from __future__ import annotations

from difflib import get_close_matches
import re
from typing import TYPE_CHECKING, Any

import pandas as pd

from alteryx2python.runtime.trace import AnchorTrace

if TYPE_CHECKING:
    from alteryx2python.ir.models import EdgeIR, NodeIR, WorkflowIR


def build_node_failure_diagnostic(
    *,
    workflow: "WorkflowIR",
    node: "NodeIR",
    exc: Exception,
    inputs: dict[str, pd.DataFrame],
    config: dict[str, object] | None = None,
) -> dict[str, Any]:
    expected_fields = _expected_fields(node, config or {})
    actual_columns = _actual_columns(inputs)
    missing_fields = [field for field in expected_fields if field not in actual_columns]
    code = _classify_error(exc, missing_fields)
    return {
        "code": code,
        "severity": "error",
        "summary": _summary(code, node, exc),
        "likely_cause": _likely_cause(code, missing_fields),
        "suggested_fix": _suggested_fix(code, node, missing_fields),
        "error": {"type": type(exc).__name__, "message": str(exc)},
        "workflow": _workflow_summary(workflow),
        "node": _node_summary(node, config or {}),
        "graph_context": _graph_context(workflow, node.node_id),
        "inputs": {
            anchor: AnchorTrace.from_frame(frame).to_dict()
            for anchor, frame in inputs.items()
            if isinstance(frame, pd.DataFrame)
        },
        "expected_fields": expected_fields,
        "missing_fields": missing_fields,
        "field_suggestions": _field_suggestions(missing_fields, actual_columns),
    }


def build_routing_failure_diagnostic(
    *,
    workflow: "WorkflowIR",
    node: "NodeIR",
    edge: "EdgeIR",
    exc: Exception,
    upstream_outputs: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    return {
        "code": "missing_upstream_output_anchor",
        "severity": "error",
        "summary": (
            f"Node {node.node_id} ({node.tool_type}) could not receive "
            f"{edge.source_node_id}:{edge.source_anchor}."
        ),
        "likely_cause": (
            "The upstream tool did not emit the anchor referenced by this workflow edge. "
            "This usually means the parsed workflow topology, macro expansion, or tool "
            "implementation no longer matches the source Alteryx workflow."
        ),
        "suggested_fix": (
            "Check the upstream node output anchors, then verify the source workflow edge "
            "and any macro/interface wiring that produced this connection."
        ),
        "error": {"type": type(exc).__name__, "message": str(exc)},
        "workflow": _workflow_summary(workflow),
        "node": _node_summary(node, {}),
        "graph_context": _graph_context(workflow, node.node_id),
        "edge": {
            "id": edge.edge_id,
            "from_node": edge.source_node_id,
            "from_anchor": edge.source_anchor,
            "to_node": edge.target_node_id,
            "to_anchor": edge.target_anchor,
        },
        "available_upstream_outputs": sorted((upstream_outputs or {}).keys()),
    }


def _workflow_summary(workflow: "WorkflowIR") -> dict[str, Any]:
    return {
        "id": workflow.workflow_id,
        "name": workflow.workflow_name,
        "source_file": workflow.source_file,
        "node_count": len(workflow.nodes),
        "edge_count": len(workflow.edges),
    }


def _node_summary(node: "NodeIR", config: dict[str, object]) -> dict[str, Any]:
    return {
        "id": node.node_id,
        "source_tool_id": node.source_tool_id,
        "tool_type": node.tool_type,
        "tool_name": node.tool_name,
        "supported_status": node.supported_status,
        "input_anchors": [anchor.name for anchor in node.input_anchors],
        "output_anchors": [anchor.name for anchor in node.output_anchors],
        "macro_context": _macro_context(node),
        "config_summary": _config_summary(node, config),
        "warnings": list(node.warnings),
        "errors": list(node.errors),
    }


def _graph_context(workflow: "WorkflowIR", node_id: str) -> dict[str, Any]:
    nodes_by_id = {node.node_id: node for node in workflow.nodes}
    incoming = []
    outgoing = []
    for edge in workflow.edges:
        edge_summary = {
            "id": edge.edge_id,
            "from": f"{edge.source_node_id}:{edge.source_anchor}",
            "to": f"{edge.target_node_id}:{edge.target_anchor}",
        }
        if edge.target_node_id == node_id:
            source = nodes_by_id.get(edge.source_node_id)
            incoming.append({**edge_summary, "source_tool_type": source.tool_type if source else None})
        if edge.source_node_id == node_id:
            target = nodes_by_id.get(edge.target_node_id)
            outgoing.append({**edge_summary, "target_tool_type": target.tool_type if target else None})
    return {"incoming": incoming, "outgoing": outgoing}


def _config_summary(node: "NodeIR", config: dict[str, object]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "node_id": config.get("node_id", node.node_id),
        "source_tool_id": config.get("source_tool_id", node.source_tool_id),
    }
    for key in (
        "file",
        "select_fields",
        "formula_fields",
        "joins",
        "mode",
        "expression",
        "node_input_anchors",
        "node_output_anchors",
    ):
        if key in config:
            summary[key] = config[key]
    return summary


def _macro_context(node: "NodeIR") -> dict[str, Any] | None:
    plugin_name = str(node.metadata.get("plugin_name", node.tool_name))
    if ".yxmc" not in plugin_name.lower() and ".yxwz" not in plugin_name.lower():
        return None
    return {
        "macro_name": plugin_name,
        "expanded": False,
        "message": "This node is backed by an Alteryx macro; inspect macro wiring if the local node context is not enough.",
    }


def _classify_error(exc: Exception, missing_fields: list[str]) -> str:
    message = str(exc).lower()
    if isinstance(exc, FileNotFoundError) or "no such file" in message:
        return "missing_input_file"
    if missing_fields or "missing input fields" in message:
        return "missing_input_fields"
    if "requires an input anchor" in message or "missing upstream result" in message:
        return "missing_input_anchor"
    if "unsupported workflow tool" in message:
        return "unsupported_tool"
    if "not supported" in message:
        return "unsupported_behavior"
    return "node_execution_failed"


def _summary(code: str, node: "NodeIR", exc: Exception) -> str:
    if code == "missing_input_fields":
        return f"Node {node.node_id} ({node.tool_type}) failed because required input columns are missing."
    if code == "missing_input_file":
        return f"Node {node.node_id} ({node.tool_type}) failed because an input file could not be read."
    if code == "unsupported_tool":
        return f"Node {node.node_id} ({node.tool_type}) is not implemented by the pipeline runtime."
    return f"Node {node.node_id} ({node.tool_type}) failed during pipeline execution: {exc}"


def _likely_cause(code: str, missing_fields: list[str]) -> str:
    if code == "missing_input_fields":
        fields = ", ".join(missing_fields) if missing_fields else "one or more required fields"
        return (
            f"Upstream data no longer provides {fields}. This is commonly caused by a "
            "column rename, changed input file, changed sheet, or upstream Select/Formula edit."
        )
    if code == "missing_input_file":
        return "The workflow input path is missing, points to the wrong file, or cannot be resolved from the workflow base directory."
    if code == "unsupported_tool":
        return "The source workflow reached an Alteryx tool that has no registered Python implementation yet."
    return "The node raised an exception after receiving its inputs. Inspect the node config and input traces."


def _suggested_fix(code: str, node: "NodeIR", missing_fields: list[str]) -> str:
    if code == "missing_input_fields":
        fields = ", ".join(missing_fields) if missing_fields else "the missing fields"
        return (
            f"Check node {node.node_id}'s upstream input schema, then update the source input, "
            f"add a rename step, or change this {node.tool_type} config to use the current name for {fields}."
        )
    if code == "missing_input_file":
        return "Verify the file path/sheet selector in the DbFileInput config and rerun with the correct input fixture."
    if code == "unsupported_tool":
        return "Add or map an implementation for this tool, or target an upstream certifiable slice while this node remains unsupported."
    return "Use the graph_context, config_summary, and input traces in this diagnostic to isolate the failing change request."


def _expected_fields(node: "NodeIR", config: dict[str, object]) -> list[str]:
    fields: list[str] = []
    if node.tool_type == "Select":
        for item in _list_config(config.get("select_fields")):
            source = item.get("source")
            if source and source != "*Unknown":
                fields.append(str(source))
    if node.tool_type == "Formula":
        for item in _list_config(config.get("formula_fields")):
            expression = item.get("expression")
            if expression:
                fields.extend(re.findall(r"\[([^\]]+)\]", str(expression)))
    return _dedupe(fields)


def _list_config(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _actual_columns(inputs: dict[str, pd.DataFrame]) -> list[str]:
    columns: list[str] = []
    for frame in inputs.values():
        if isinstance(frame, pd.DataFrame):
            columns.extend(str(column) for column in frame.columns)
    return _dedupe(columns)


def _field_suggestions(missing_fields: list[str], actual_columns: list[str]) -> dict[str, list[str]]:
    lower_to_actual = {column.lower(): column for column in actual_columns}
    lower_columns = list(lower_to_actual)
    suggestions: dict[str, list[str]] = {}
    for field in missing_fields:
        matches = get_close_matches(field.lower(), lower_columns, n=3, cutoff=0.45)
        suggestions[field] = [lower_to_actual[match] for match in matches]
    return suggestions


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
