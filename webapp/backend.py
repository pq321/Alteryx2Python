"""Canonical compilation and execution services for the local Web App."""
from __future__ import annotations

import base64
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
from threading import RLock
from xml.etree import ElementTree as ET

from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.expressions.errors import UnsupportedExpressionError
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.tools.registry import TOOL_REGISTRY

try:
    from .graph_compiler import compile_graph_to_yxmd
    from .tool_palette import blocked_reason
    from .workflow_documents import source_path
except ImportError:
    from graph_compiler import compile_graph_to_yxmd
    from tool_palette import blocked_reason
    from workflow_documents import source_path


EXECUTION_LOCK = RLock()


class ApiError(ValueError):
    def __init__(self, code, message, *, status=400, details=None):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details or {}


def error_payload(exc):
    if isinstance(exc, ApiError):
        return {"error": str(exc), "errorType": type(exc).__name__, "code": exc.code, "details": exc.details}, exc.status
    if isinstance(exc, PermissionError):
        code, status = "permission_denied", 403
    elif isinstance(exc, (NotImplementedError, ImportError, UnsupportedExpressionError)):
        code, status = "runtime_unavailable", 422
    elif isinstance(exc, (ValueError, KeyError, TypeError, SyntaxError)):
        code, status = "invalid_configuration", 400
    else:
        code, status = "execution_failed", 422
    return {"error": str(exc), "errorType": type(exc).__name__, "code": code, "details": {}}, status


def runtime_settings(graph):
    supplied = graph.get("runtime", {})
    if not isinstance(supplied, dict):
        raise ValueError("runtime must be an object")
    supported = {"answers", "constants", "delivery_profile", "allowed_commands", "input_dir", "command_working_dir",
                 "event_working_dir", "command_timeout", "allow_external_runtimes"}
    unknown = set(supplied) - supported
    if unknown:
        raise ValueError(f"Unknown runtime settings: {sorted(unknown)}")
    settings = {"answers": {}, "constants": {}, "delivery_profile": "html-draft-v1", "allowed_commands": [], **supplied}
    for key in ("answers", "constants"):
        if not isinstance(settings[key], dict):
            raise ValueError(f"runtime.{key} must be an object")
    allowed = settings["allowed_commands"]
    if not isinstance(allowed, list) or any(not isinstance(item, str) or not item.strip() for item in allowed):
        raise ValueError("runtime.allowed_commands must be an explicit array of executable paths or names")
    if settings["delivery_profile"] not in {"html-draft-v1", "html-smtp-v1"}:
        raise ValueError("Unsupported delivery profile")
    if "allow_external_runtimes" in supplied and not isinstance(supplied["allow_external_runtimes"], bool):
        raise ValueError("runtime.allow_external_runtimes must be Boolean")
    if "command_timeout" in supplied:
        timeout = supplied["command_timeout"]
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
            raise ValueError("runtime.command_timeout must be between 0 and 3600 seconds")
    if graph.get("parameterMode", "dynamic") not in {"dynamic", "specialized"}:
        raise ValueError("parameterMode must be dynamic or specialized")
    return settings


def parse_graph(graph, base_dir):
    xml = compile_graph_to_yxmd(graph)
    workflow = XmlWorkflowParser().parse_xml(xml, source_path(graph, base_dir))
    return xml, workflow


def binding_gaps(workflow):
    from alteryx2python.runtime.app_config import INTERFACE, LAYOUT, question_manifest
    root = ET.fromstring(workflow.source_xml)
    kinds = {node.tool_type for node in workflow.nodes}
    gaps = []
    if kinds & (INTERFACE - LAYOUT - {"Action", "Condition", "Error", "QuestionTab"}) and not question_manifest(root):
        gaps.append("Interface value tools require grouped Properties/RuntimeProperties/Questions configuration")
    actions = root.find("Properties/RuntimeProperties/Actions")
    if kinds & {"Action", "Condition"} and (actions is None or actions.find(".//Action") is None):
        gaps.append("Action/Condition tools require grouped Properties/RuntimeProperties/Actions configuration")
    return gaps


def compile_workflow(graph, base_dir):
    settings = runtime_settings(graph)
    xml, workflow = parse_graph(graph, base_dir)
    result = {"name": graph.get("name", "workflow"), "yxmd": xml, "python": "", "unsupported": [], "blockers": [],
              "compiler": "ReadablePythonGenerator", "phase2Status": "blocked"}
    try:
        gaps = binding_gaps(workflow)
        if gaps:
            raise UnsupportedLowering("; ".join(gaps))
        options = {"answers": settings["answers"], "constants": settings["constants"],
                   "parameter_mode": graph.get("parameterMode", "dynamic"),
                   "delivery_profile": settings["delivery_profile"]}
        artifact = ReadablePythonGenerator().generate(workflow, **options)
        result.update(python=artifact.source, manifest=artifact.manifest, phase2Status="compiled")
    except (UnsupportedLowering, NotImplementedError, ImportError, UnsupportedExpressionError) as exc:
        result["unsupported"] = [str(exc)]
        result["blockers"] = [{"code": "phase2_unsupported", "errorType": type(exc).__name__, "message": str(exc)}]
    return result


def _check_runtime_nodes(workflow, settings, visited=None, *, defer_binding=False):
    """Reject metadata placeholders and unapproved external interpreters."""
    from alteryx2python.runtime.app_config import prepare_workflow
    from alteryx2python.runtime.variables import workflow_variables, variable_scope

    visited = set() if visited is None else visited
    if workflow.source_file in visited:
        return
    visited = visited | {workflow.source_file}
    gaps = binding_gaps(workflow)
    if gaps:
        raise ApiError("configuration_binding_missing", "; ".join(gaps), details={"bindings": gaps})
    with variable_scope(workflow_variables(workflow, settings["constants"])):
        # Batch controls are bound to each data row by the canonical executor.
        prepared = workflow if defer_binding else prepare_workflow(workflow, settings["answers"])
    from alteryx2python.runtime.scheduling import container_guards
    nodes_by_id = {node.node_id: node for node in prepared.nodes}
    for node in prepared.nodes:
        if None in container_guards(node, nodes_by_id, prepared.edges):
            continue
        if node.tool_type in TOOL_REGISTRY.list_tool_types():
            reason = blocked_reason(TOOL_REGISTRY.get(node.tool_type))
            if reason:
                raise ApiError("runtime_unavailable", f"{node.tool_type} #{node.node_id}: {reason}", status=422)
        elif not node.tool_type.startswith("Macro_"):
            raise ApiError("runtime_unavailable", f"No runtime implementation for {node.tool_type} #{node.node_id}", status=422)
        config = node.config.get("normalized", node.config)
        if node.tool_type.startswith("Macro_"):
            raw = Path(str(config.get("macro_path", "")))
            candidates = [raw] if raw.is_absolute() else [Path(config.get("base_dir", ".")) / raw,
                                                        Path("D:/Alteryx/bin/RuntimeData/Macros") / raw]
            path = next((item.resolve() for item in candidates if item.is_file()), None)
            if path is None:
                raise ApiError("macro_unavailable", f"Macro dependency is missing: {raw}", status=422)
            from alteryx2python.parser.tool_parsers.common import as_list
            answers = dict(config.get("macro_answers", {}))
            for value in as_list(config.get("Value", [])):
                if isinstance(value, dict):
                    attributes = value.get("attributes", value.get("@attributes", {}))
                    name = attributes.get("name", value.get("@name"))
                    if name:
                        answers[name] = value.get("text", value.get("#text", ""))
            child = XmlWorkflowParser().parse(path)
            batch = ET.fromstring(child.source_xml).find("Properties/RuntimeProperties/BatchMacro")
            child_settings = {**settings, "answers": answers, "constants": {}}
            _check_runtime_nodes(child, child_settings, visited, defer_binding=defer_binding or batch is not None)
        if node.tool_type in {"R", "JupyterFlow", "CustomSpark"}:
            if not settings.get("allow_external_runtimes"):
                raise PermissionError(f"{node.tool_type} requires explicit runtime.allow_external_runtimes permission")
            if node.tool_type == "R":
                executable = str(config.get("rscript") or config.get("executable") or shutil.which("Rscript") or "")
                allowed = {Path(shutil.which(value) or value).resolve() for value in settings["allowed_commands"]}
                if not executable or Path(shutil.which(executable) or executable).resolve() not in allowed:
                    raise PermissionError("R interpreter must also be in runtime.allowed_commands")
        if node.tool_type == "Runner":
            target = config.get("workflow") or config.get("path")
            if target:
                path = Path(str(target))
                if not path.is_absolute():
                    path = Path(config.get("base_dir", ".")) / path
                _check_runtime_nodes(XmlWorkflowParser().parse(path.resolve()), settings, visited)


def preview(node_id, anchor, frame):
    return {"node": node_id, "anchor": anchor, "columns": [str(c) for c in frame.columns],
            "rows": json.loads(frame.head(500).to_json(orient="split", date_format="iso"))["data"],
            "rowCount": len(frame), "csv": frame.to_csv(index=False)}


def run_workflow(graph, base_dir):
    settings = runtime_settings(graph)
    compiled = compile_workflow(graph, base_dir)
    _, workflow = parse_graph(graph, base_dir)
    _check_runtime_nodes(workflow, settings)
    with tempfile.TemporaryDirectory(prefix="ayx_editor_") as directory:
        output = Path(directory)
        context = WorkflowContext(runtime_config={"input_dir": str(Path(workflow.source_file).parent), **settings,
                                                  "execute_commands": True, "redirect_sinks": True, "output_dir": str(output)})
        stdout = io.StringIO()
        try:
            # Python Tool programs may print. Serialize capture so concurrent runs
            # cannot redirect each other's process-level stdout.
            with EXECUTION_LOCK, redirect_stdout(stdout):
                result = run_workflow_graph(workflow, context)
        except Exception as exc:
            payload, status = error_payload(exc)
            raise ApiError(payload["code"], str(exc), status=status,
                           details={"causeType": type(exc).__name__, "warnings": context.warnings,
                                    "errors": context.errors, "diagnostics": context.diagnostics, "stdout": stdout.getvalue()}) from exc
        previews = [preview(node_id, anchor, frame) for node_id, item in result.node_results.items() for anchor, frame in item.outputs.items()]
        for node in workflow.nodes:
            if node.tool_type == "DbFileOutput" and node.node_id in result.node_results:
                trace = result.node_results[node.node_id].trace
                path = trace.config.get("resolved_path") if trace else None
                if path and Path(path).is_file():
                    import pandas as pd
                    from alteryx2python.tools.dbfileoutput import _format_option
                    config = node.config.get("normalized", {})
                    codepage = _format_option(config, "CodePage", "28591")
                    encoding = {"65001": "utf-8", "1200": "utf-16", "28591": "latin-1"}.get(codepage, f"cp{codepage}")
                    if _format_option(config, "HeaderRow", "True").lower() == "true":
                        frame = pd.read_csv(path, dtype=object, keep_default_na=False, encoding=encoding,
                                            sep=_format_option(config, "Delimeter", ","))
                        previews.append(preview(node.node_id, "Input", frame))
                        continue
                for edge in workflow.edges:
                    upstream = result.node_results.get(edge.source_node_id)
                    if edge.target_node_id == node.node_id and upstream and edge.source_anchor in upstream.outputs:
                        previews.append(preview(node.node_id, "Input", upstream.outputs[edge.source_anchor]))
        final = previews[-1] if previews else {"columns": [], "rows": []}
        artifacts, remaining = [], 20 * 1024 * 1024
        for path in sorted(output.rglob("*")):
            if path.is_file():
                size = path.stat().st_size
                artifact = {"name": path.relative_to(output).as_posix(), "size": size, "available": size <= remaining}
                if artifact["available"]:
                    artifact["content"] = base64.b64encode(path.read_bytes()).decode("ascii")
                    remaining -= size
                artifacts.append(artifact)
        return {**compiled, "previews": previews, "columns": final["columns"], "rows": final["rows"],
                "warnings": [*workflow.warnings, *context.warnings, *result.warnings], "diagnostics": context.diagnostics,
                "artifacts": artifacts, "stdout": stdout.getvalue(), "executionOrder": result.execution_order, "runtimeStatus": "executed"}
