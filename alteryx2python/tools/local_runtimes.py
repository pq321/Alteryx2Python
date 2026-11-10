"""Explicit local adapters for external-runtime tools."""

from __future__ import annotations
import json, os, subprocess, tempfile, shutil
import uuid
from pathlib import Path
from typing import Any
import pandas as pd
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.unavailable import ToolUnavailableError

ANCHORS = {
    "R": (("Input",), ("Output",)),
    "Runner": ((), ("Output",)),
    "JupyterFlow": (("Input",), ("Output",)),
    "CustomSpark": (("Input",), ("Output",)),
}


def _record(context, typ, inputs, outputs, config):
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=typ,
        source_tool_id=config.get("source_tool_id"),
        inputs=inputs,
        outputs=outputs,
        status="success",
        config=dict(config),
    )


def r_tool(inputs, config, context):
    runtime = context.runtime_config or {}
    exe = (
        config.get("rscript")
        or config.get("executable")
        or runtime.get("rscript")
        or shutil.which("Rscript")
    )
    code = config.get("code") or config.get("RCode")
    if isinstance(code, dict):
        code = code.get("text", code.get("#text", ""))
    if not exe:
        raise ToolUnavailableError(
            "R requires an installed/configured Rscript interpreter"
        )
    if not Path(str(exe)).exists():
        raise ToolUnavailableError(f"Rscript not found: {exe}")
    if not code:
        raise ValueError("R requires configured rscript and code")
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        inp = d / "input.csv"
        out = d / "output.csv"
        sentinel = "__A2P_NULL_" + uuid.uuid4().hex + "__"
        if "Input" in inputs:
            inputs["Input"].to_csv(inp, index=False, na_rep=sentinel)
        # Public R-tool bridge names; no vendor implementation is copied.
        bridge = (
            f'read.Alteryx <- function(connection="#1", ...) {{ if (!connection %in% c("#1", "1")) stop("Local R profile supports one input"); read.csv(Sys.getenv("ALTERYX_INPUT"), check.names=FALSE, stringsAsFactors=FALSE, na.strings="{sentinel}") }}\n'
            f'write.Alteryx <- function(data, connection=1, ...) {{ if (connection != 1) stop("Local R profile supports one output"); write.csv(data, Sys.getenv("ALTERYX_OUTPUT"), row.names=FALSE, na="{sentinel}") }}\n'
        )
        script = d / "run.R"
        script.write_text(bridge + str(code), encoding="utf-8")
        env = os.environ.copy()
        env.update({"ALTERYX_INPUT": str(inp), "ALTERYX_OUTPUT": str(out)})
        subprocess.run(
            [str(exe), "--vanilla", str(script)],
            check=True,
            env=env,
            capture_output=True,
            text=True,
            timeout=float(config.get("timeout", 120)),
        )
        if not out.exists():
            raise RuntimeError("R code did not write ALTERYX_OUTPUT")
        result = {
            "Output": pd.read_csv(out, keep_default_na=False).replace(sentinel, None)
        }
    _record(context, "R", inputs, result, {**config, "executedRcode": str(code)})
    return result


def runner_tool(inputs, config, context):
    path = config.get("workflow") or config.get("path")
    if path and not Path(str(path)).is_absolute():
        path = Path(config.get("base_dir", ".")) / str(path)
    if not path or not Path(str(path)).exists():
        raise ToolUnavailableError("Runner requires an existing local .yxmd workflow")
    path = Path(path).resolve()
    runtime = dict(context.runtime_config or {})
    chain = runtime.get("_runner_chain", [])
    if str(path) in chain:
        raise ValueError("Recursive Runner workflow inclusion")
    runtime["_runner_chain"] = [*chain, str(path)]
    from alteryx2python.parser.xml_parser import XmlWorkflowParser
    from alteryx2python.runtime.executor import run_workflow_graph
    from alteryx2python.runtime.context import WorkflowContext

    workflow = XmlWorkflowParser().parse(Path(str(path)))
    target = config.get("target_node") or config.get("output_node")
    if target:
        target = str(target)
    else:
        upstream = {edge.source_node_id for edge in workflow.edges}
        terminals = [
            node.node_id
            for node in workflow.nodes
            if node.node_id not in upstream
            and node.tool_type not in {"TextBox", "HtmlBox", "ToolContainer"}
        ]
        if len(terminals) != 1:
            raise ValueError(
                "Runner requires target_node when the workflow has multiple terminal nodes"
            )
        target = terminals[0]
    result = run_workflow_graph(
        workflow, WorkflowContext(runtime_config=runtime), target_node_ids={target}
    )
    frames = result.node_results[target].outputs
    anchor = config.get("output_anchor")
    if anchor is None and len(frames) == 1:
        anchor = next(iter(frames))
    if anchor not in frames:
        raise ValueError(
            "Runner requires an existing output_anchor for the target node"
        )
    outputs = {"Output": frames[anchor].copy()}
    _record(context, "Runner", inputs, outputs, config)
    return outputs


def jupyterflow_tool(inputs, config, context):
    try:
        from nbclient import NotebookClient
    except ImportError as exc:
        raise ToolUnavailableError("JupyterFlow requires nbclient") from exc
    path = config.get("notebook") or config.get("path")
    if not path:
        raise ValueError("JupyterFlow requires notebook path")
    import nbformat

    with tempfile.TemporaryDirectory() as td:
        inp, out = Path(td) / "input.csv", Path(td) / "output.csv"
        if "Input" in inputs:
            inputs["Input"].to_csv(inp, index=False)
        nb = nbformat.read(path, as_version=4)
        nb.cells.insert(
            0,
            nbformat.v4.new_code_cell(
                f"import os\nALTERYX_INPUT={str(inp)!r}\nALTERYX_OUTPUT={str(out)!r}"
            ),
        )
        client = NotebookClient(nb, timeout=int(config.get("timeout", 600)))
        client.execute()
        if not out.exists():
            raise RuntimeError("JupyterFlow notebook did not create ALTERYX_OUTPUT")
        result = {"Output": pd.read_csv(out)}
    _record(context, "JupyterFlow", inputs, result, config)
    return result


def customspark_tool(inputs, config, context):
    code = config.get("code") or config.get("python")
    if not code:
        raise ValueError("CustomSpark requires configured Python code")
    try:
        spark = config.get("spark_session")
    except Exception:
        spark = None
    if spark is None:
        try:
            from pyspark.sql import SparkSession

            spark = SparkSession.builder.master("local[2]").getOrCreate()
        except Exception as exc:
            raise ToolUnavailableError(
                "CustomSpark requires pyspark or spark_session"
            ) from exc
    scope = {"spark": spark, "input_df": inputs.get("Input"), "result": None}
    exec(str(code), scope)
    result = scope.get("result")
    if result is None:
        raise RuntimeError("CustomSpark code must assign result")
    if hasattr(result, "toPandas"):
        result = result.toPandas()
    result = {"Output": result}
    _record(context, "CustomSpark", inputs, result, config)
    return result


class _Runtime(BaseTool):
    def execute(self, inputs, config, context):
        return IMPLEMENTATIONS[self.tool_type](inputs, config, context)


TOOL_CLASSES = {
    n: type(
        n, (_Runtime,), {"tool_type": n, "input_anchors": a[0], "output_anchors": a[1]}
    )
    for n, a in ANCHORS.items()
}
IMPLEMENTATIONS = {
    "R": r_tool,
    "Runner": runner_tool,
    "JupyterFlow": jupyterflow_tool,
    "CustomSpark": customspark_tool,
}
PARSERS = {}
