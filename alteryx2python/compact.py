from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from alteryx2python.ir.models import NodeIR, WorkflowIR


COMPACT_WORKFLOW_VERSION = "0.1.0"


def build_compact_workflow(workflow: WorkflowIR) -> dict[str, Any]:
    """Build an AI-facing workflow view without raw Alteryx XML/UI shell data."""
    edges_by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    edges_by_target: dict[str, list[dict[str, str]]] = defaultdict(list)
    edges: list[dict[str, str]] = []
    for edge in workflow.edges:
        compact_edge = {
            "id": edge.edge_id,
            "from_node": edge.source_node_id,
            "from_anchor": edge.source_anchor,
            "to_node": edge.target_node_id,
            "to_anchor": edge.target_anchor,
        }
        edges.append(compact_edge)
        edges_by_source[edge.source_node_id].append(compact_edge)
        edges_by_target[edge.target_node_id].append(compact_edge)

    node_ids = [node.node_id for node in workflow.nodes]
    graph = _graph_summary(node_ids, edges)
    return {
        "format": "alteryx2python.compact_workflow",
        "version": COMPACT_WORKFLOW_VERSION,
        "workflow": {
            "id": workflow.workflow_id,
            "name": workflow.workflow_name,
            "source_file": workflow.source_file,
            "classification": workflow.classification,
            "node_count": len(workflow.nodes),
            "edge_count": len(workflow.edges),
        },
        "graph": graph,
        "nodes": [
            _compact_node(
                node,
                incoming_edges=edges_by_target.get(node.node_id, []),
                outgoing_edges=edges_by_source.get(node.node_id, []),
            )
            for node in workflow.nodes
        ],
        "edges": edges,
        "external_dependencies": list(workflow.external_dependencies),
        "warnings": list(workflow.warnings),
    }


def _compact_node(
    node: NodeIR,
    *,
    incoming_edges: list[dict[str, str]],
    outgoing_edges: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "id": node.node_id,
        "source_tool_id": node.source_tool_id,
        "type": node.tool_type,
        "plugin": node.tool_name,
        "supported_status": node.supported_status,
        "inputs": [anchor.name for anchor in node.input_anchors],
        "outputs": [anchor.name for anchor in node.output_anchors],
        "incoming": [
            {
                "from": f"{edge['from_node']}:{edge['from_anchor']}",
                "to": f"{edge['to_node']}:{edge['to_anchor']}",
            }
            for edge in incoming_edges
        ],
        "outgoing": [
            {
                "from": f"{edge['from_node']}:{edge['from_anchor']}",
                "to": f"{edge['to_node']}:{edge['to_anchor']}",
            }
            for edge in outgoing_edges
        ],
        "config_summary": _config_summary(node),
        "schema_summary": _schema_summary(node.expected_output_schema),
        "warnings": list(node.warnings),
        "errors": list(node.errors),
    }


def _graph_summary(node_ids: list[str], edges: list[dict[str, str]]) -> dict[str, Any]:
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if edge["to_node"] in incoming:
            incoming[edge["to_node"]] += 1
        outgoing.setdefault(edge["from_node"], []).append(edge["to_node"])

    roots = [node_id for node_id in node_ids if incoming.get(node_id, 0) == 0]
    leaves = [node_id for node_id in node_ids if not outgoing.get(node_id)]
    return {
        "roots": roots,
        "leaves": leaves,
        "topological_order": _topological_order(node_ids, edges),
    }


def _topological_order(node_ids: list[str], edges: list[dict[str, str]]) -> list[str]:
    node_id_set = set(node_ids)
    indegree = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        source = edge["from_node"]
        target = edge["to_node"]
        if source not in node_id_set or target not in node_id_set:
            continue
        outgoing[source].append(target)
        indegree[target] += 1

    queue = deque(node_id for node_id in node_ids if indegree[node_id] == 0)
    order: list[str] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for target in outgoing.get(node_id, []):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(node_ids):
        return []
    return order


def _config_summary(node: NodeIR) -> dict[str, Any]:
    normalized = node.config.get("normalized", {})
    if not isinstance(normalized, dict):
        return {}

    tool_type = node.tool_type
    if tool_type == "DbFileInput":
        return {
            "file": normalized.get("file"),
            "file_name": _file_name(normalized.get("file")),
            "file_attributes": normalized.get("file_attributes", {}),
        }
    if tool_type == "DbFileOutput":
        return {
            "file": normalized.get("file"),
            "file_name": _file_name(normalized.get("file")),
            "file_format": normalized.get("file_format"),
        }
    if tool_type == "Select":
        return {"select_fields": normalized.get("select_fields", [])}
    if tool_type == "Formula":
        return {"formula_fields": normalized.get("formula_fields", [])}
    if tool_type == "Filter":
        return {
            "expression": normalized.get("expression"),
            "mode": normalized.get("mode"),
        }
    if tool_type == "Join":
        return {
            "join_by_record_pos": normalized.get("join_by_record_pos"),
            "joins": normalized.get("joins", []),
            "output_connection": normalized.get("output_connection"),
            "select_fields": normalized.get("select_fields", []),
        }
    if tool_type == "Union":
        return {
            "mode": normalized.get("mode"),
            "by_name_error_mode": normalized.get("by_name_error_mode"),
            "by_name_output_mode": normalized.get("by_name_output_mode"),
            "set_output_order": normalized.get("set_output_order"),
        }
    if tool_type == "TextInput":
        rows = normalized.get("rows", [])
        fields = normalized.get("fields", [])
        return {
            "fields": fields,
            "row_count": len(rows) if isinstance(rows, list) else None,
        }
    return {
        key: value
        for key, value in normalized.items()
        if key not in {"base_dir"} and not key.startswith("raw")
    }


def _schema_summary(schema: dict[str, Any]) -> dict[str, Any]:
    if not schema:
        return {}
    if "fields" in schema:
        return {"Output": _fields_summary(schema.get("fields", []))}
    summary: dict[str, Any] = {}
    for anchor, anchor_schema in schema.items():
        if isinstance(anchor_schema, dict):
            summary[str(anchor)] = _fields_summary(anchor_schema.get("fields", []))
    return summary


def _fields_summary(fields: Any) -> list[dict[str, Any]]:
    if not isinstance(fields, list):
        return []
    compact_fields: list[dict[str, Any]] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        compact_fields.append(
            {
                key: field[key]
                for key in ("name", "type", "size", "scale")
                if key in field
            }
        )
    return compact_fields


def _file_name(value: Any) -> str | None:
    if not value:
        return None
    return Path(str(value).split("|||", 1)[0]).name
