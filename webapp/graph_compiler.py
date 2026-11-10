"""JSON graph -> .yxmd compiler for the visual workflow editor.

The editor frontend exchanges plain JSON documents (nodes + edges + configs);
this module renders them into official Alteryx .yxmd XML through the same
WorkflowBuilder used by the equivalence test suite, so anything drawn on the
canvas is a real, Designer-loadable workflow.
"""
from __future__ import annotations

from typing import Any

from alteryx2python.workflow_generator import WorkflowBuilder


def compile_graph_to_yxmd(graph: dict[str, Any]) -> str:
    """Render an editor graph document into .yxmd XML."""
    builder = WorkflowBuilder()
    node_ids: dict[str, int] = {}

    for node in graph.get("nodes", []):
        node_ids[str(node["id"])] = _add_node(builder, node)

    for edge in graph.get("edges", []):
        source = node_ids.get(str(edge["from"]))
        target = node_ids.get(str(edge["to"]))
        if source is None or target is None:
            raise ValueError(f"edge references unknown node: {edge}")
        builder.connect(
            source,
            target,
            source_anchor=str(edge.get("fromAnchor", "Output")),
            target_anchor=str(edge.get("toAnchor", "Input")),
        )
    return builder.render()


def _add_node(builder: WorkflowBuilder, node: dict[str, Any]) -> int:
    kind = str(node.get("type", ""))
    config = node.get("config") or {}
    position = (int(node.get("x", 250)), int(node.get("y", 186)))
    if kind == "TextInput":
        fields = [str(field) for field in config.get("fields", [])]
        rows = [list(row) for row in config.get("rows", [])]
        return builder.add_text_input(fields, rows, position)
    if kind == "Formula":
        expressions = [
            (str(item.get("field", "")), str(item.get("type", "String")), str(item.get("size", "")), str(item.get("expression", "")))
            for item in config.get("expressions", [])
        ]
        return builder.add_formula(expressions, position)
    if kind == "Filter":
        return builder.add_filter(str(config.get("expression", "")), position)
    if kind == "Select":
        fields = [(str(item.get("field", "")), str(item.get("selected", "True"))) for item in config.get("fields", [])]
        return builder.add_select(fields, include_unknown=bool(config.get("includeUnknown", False)), position=position)
    if kind == "Sort":
        order = [(str(item.get("field", "")), str(item.get("order", "Ascending"))) for item in config.get("order", [])]
        return builder.add_sort(order, position)
    if kind == "Summarize":
        actions = [
            (str(item.get("field", "")), str(item.get("action", "GroupBy")), str(item.get("rename", "")))
            for item in config.get("actions", [])
        ]
        return builder.add_summarize(actions, position)
    if kind == "Join":
        return builder.add_join(
            str(config.get("leftField", "")), str(config.get("rightField", "")), position
        )
    if kind == "Union":
        return builder.add_union(position)
    if kind == "RecordID":
        return builder.add_record_id(position)
    if kind == "Sample":
        return builder.add_sample(str(config.get("mode", "First")), str(config.get("n", "10")), position)
    if kind == "Unique":
        return builder.add_unique(str(config.get("field", "")), position)
    if kind == "CrossTab":
        return builder.add_crosstab(
            str(config.get("groupBy", "")),
            str(config.get("header", "")),
            str(config.get("dataField", "")),
            str(config.get("method", "First")),
            position,
        )
    if kind == "Transpose":
        return builder.add_transpose(
            [str(field) for field in config.get("keyFields", [])],
            [str(field) for field in config.get("dataFields", [])],
            position,
        )
    if kind == "RegEx":
        return builder.add_regex(
            str(config.get("field", "")),
            str(config.get("pattern", "")),
            [(str(config.get("outputField", "Parsed")), "V_String", 256)],
            position=position,
        )
    if kind == "DateTime":
        return builder.add_datetime(
            str(config.get("inputField", "")),
            str(config.get("outputField", "")),
            str(config.get("format", "yyyy-MM-dd")),
            position,
        )
    if kind == "MultiRowFormula":
        return builder.add_multi_row_formula(
            str(config.get("expression", "")), str(config.get("fieldName", "NewField")), position=position
        )
    if kind == "RunningTotal":
        return builder.add_running_total(str(config.get("field", "")), position=position)
    if kind == "Rank":
        return builder.add_rank(str(config.get("field", "")), str(config.get("order", "Descending")), position)
    if kind == "TextToColumns":
        return builder.add_text_to_columns(
            str(config.get("field", "")), str(config.get("delimiter", ",")), position
        )
    if kind == "DbFileOutput":
        return builder.add_csv_output(str(config.get("file", "output.csv")), position)
    raise ValueError(f"unsupported editor tool type: {kind}")
