from __future__ import annotations

from typing import Any

from alteryx2python.ir.models import NodeIR, WorkflowIR


REPORT_TEXT_TOOLS = {"PortfolioComposerText", "ReportHeader", "ReportFooter", "HtmlBox"}
REPORT_TABLE_TOOLS = {"PortfolioComposerTable", "BasicDataProfile", "FieldInfo"}
REPORT_LAYOUT_TOOLS = {"PortfolioComposerLayout", "VisualLayout", "Overlay"}
REPORT_RENDER_TOOLS = {"PortfolioComposerRender", "AlteryxReportChartGui", "PlotlyCharting"}
ATTACHMENT_TOOLS = {"DbFileOutput", "PortfolioComposerRender"}


def build_support_map(workflow: WorkflowIR) -> dict[str, Any]:
    """Build a change-request index for support engineers."""
    surfaces = [_surface_for_node(workflow, node) for node in workflow.nodes]
    surfaces = [surface for surface in surfaces if surface is not None]
    return {
        "format": "alteryx2python.support_map",
        "version": "0.1.0",
        "workflow": {
            "id": workflow.workflow_id,
            "name": workflow.workflow_name,
            "source_file": workflow.source_file,
            "node_count": len(workflow.nodes),
            "surface_count": len(surfaces),
        },
        "surfaces": surfaces,
        "change_request_index": {
            "inputs": _node_ids_for_role(surfaces, "input"),
            "outputs": _node_ids_for_role(surfaces, "output"),
            "body_candidates": _node_ids_for_role(surfaces, "body"),
            "table_candidates": _node_ids_for_role(surfaces, "table"),
            "layout_candidates": _node_ids_for_role(surfaces, "layout"),
            "attachment_candidates": _node_ids_for_role(surfaces, "attachment"),
            "subject_candidates": _node_ids_for_role(surfaces, "subject"),
        },
    }


def _surface_for_node(workflow: WorkflowIR, node: NodeIR) -> dict[str, Any] | None:
    config = _normalized_config(node)
    roles = _roles(node, config)
    if not roles:
        return None
    return {
        "node_id": node.node_id,
        "source_tool_id": node.source_tool_id,
        "tool_type": node.tool_type,
        "roles": roles,
        "editable_fields": _editable_fields(node.tool_type, config),
        "macro_context": _macro_context(node),
        "config_summary": _config_summary(config),
        "graph_context": _graph_context(workflow, node.node_id),
    }


def _roles(node: NodeIR, config: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    tool_type = node.tool_type
    lower_keys = {str(key).lower() for key in config}
    lower_values = " ".join(str(value).lower() for value in config.values() if isinstance(value, str))
    if tool_type == "DbFileInput":
        roles.append("input")
    if tool_type in ATTACHMENT_TOOLS:
        roles.extend(["output", "attachment"])
    if tool_type in REPORT_TEXT_TOOLS or tool_type in {"TextInput", "Formula"} and "body" in lower_values:
        roles.append("body")
    if tool_type in REPORT_TABLE_TOOLS:
        roles.append("table")
    if tool_type in REPORT_LAYOUT_TOOLS:
        roles.append("layout")
    if tool_type in REPORT_RENDER_TOOLS:
        roles.append("render")
    if "subject" in lower_keys or "subject" in lower_values:
        roles.append("subject")
    if {"to", "cc", "bcc", "recipient", "recipients"} & lower_keys:
        roles.append("recipient")
    return _dedupe(roles)


def _editable_fields(tool_type: str, config: dict[str, Any]) -> list[str]:
    if tool_type == "DbFileInput":
        return [field for field in ("file", "format_specific_options", "file_attributes") if field in config]
    if tool_type == "DbFileOutput":
        return [field for field in ("file", "file_format") if field in config]
    if tool_type == "PortfolioComposerText":
        return [field for field in ("message", "rich_text", "header_field", "output_field") if field in config]
    if tool_type == "PortfolioComposerTable":
        return [field for field in ("table_fields", "pivot_table_fields", "grouping_fields", "table_mode") if field in config]
    if tool_type == "PortfolioComposerRender":
        return [field for field in ("output_file", "temp_file_type", "data_field", "header_field", "footer_field") if field in config]
    if tool_type in {"ReportHeader", "ReportFooter"}:
        return [field for field in ("header_text", "copyright_text", "info_text", "image_file") if field in config]
    if tool_type == "HtmlBox":
        return sorted(config)
    return sorted(
        key
        for key in config
        if any(token in key.lower() for token in ("subject", "body", "message", "file", "field", "table"))
    )


def _normalized_config(node: NodeIR) -> dict[str, Any]:
    normalized = node.config.get("normalized", node.config)
    return normalized if isinstance(normalized, dict) else {}


def _macro_context(node: NodeIR) -> dict[str, Any] | None:
    plugin_name = str(node.metadata.get("plugin_name", node.tool_name))
    if ".yxmc" not in plugin_name.lower() and ".yxwz" not in plugin_name.lower():
        return None
    return {
        "macro_name": plugin_name,
        "expanded": False,
        "message": "Macro-backed node; inspect macro input/output wiring for deep failures.",
    }


def _config_summary(config: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in config.items():
        if key == "base_dir" or key.startswith("raw"):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = value
        elif isinstance(value, list):
            summary[key] = value if len(value) <= 10 else {"count": len(value)}
        elif isinstance(value, dict):
            summary[key] = {sub_key: sub_value for sub_key, sub_value in list(value.items())[:10]}
    return summary


def _graph_context(workflow: WorkflowIR, node_id: str) -> dict[str, Any]:
    nodes_by_id = {node.node_id: node for node in workflow.nodes}
    incoming = []
    outgoing = []
    for edge in workflow.edges:
        if edge.target_node_id == node_id:
            source = nodes_by_id.get(edge.source_node_id)
            incoming.append(
                {
                    "from": f"{edge.source_node_id}:{edge.source_anchor}",
                    "to": f"{edge.target_node_id}:{edge.target_anchor}",
                    "source_tool_type": source.tool_type if source else None,
                }
            )
        if edge.source_node_id == node_id:
            target = nodes_by_id.get(edge.target_node_id)
            outgoing.append(
                {
                    "from": f"{edge.source_node_id}:{edge.source_anchor}",
                    "to": f"{edge.target_node_id}:{edge.target_anchor}",
                    "target_tool_type": target.tool_type if target else None,
                }
            )
    return {"incoming": incoming, "outgoing": outgoing}


def _node_ids_for_role(surfaces: list[dict[str, Any]], role: str) -> list[str]:
    return [surface["node_id"] for surface in surfaces if role in surface["roles"]]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
