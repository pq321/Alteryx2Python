from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def _cell_text(node: Any) -> str:
    if isinstance(node, dict):
        return str(node.get("text", ""))
    if node is None:
        return ""
    return str(node)


def parse_arrange_config(raw_config: dict[str, Any]) -> ToolParserResult:
    columns = [
        {
            "name": str(attributes(column).get("name", "")),
            "type": str(attributes(column).get("type", "")),
            "context": str(attributes(column).get("context", "")),
        }
        for column in as_list(child(child(child(raw_config, "OutputFields"), "Columns"), "Column"))
    ]
    rows = [
        [_cell_text(cell) for cell in as_list(child(row, "c"))]
        for row in as_list(child(child(child(raw_config, "OutputFields"), "Data"), "r"))
    ]
    key_fields = [
        str(attributes(field).get("name", ""))
        for field in as_list(child(child(raw_config, "KeyFields"), "Field"))
        if attributes(field).get("name")
    ]
    return ToolParserResult(
        normalized_config={"key_fields": key_fields, "output_columns": columns, "output_rows": rows}
    )
