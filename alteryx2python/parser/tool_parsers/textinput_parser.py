from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_textinput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    field_nodes = as_list(child(raw_config, "Fields").get("Field", []))
    row_nodes = as_list(child(raw_config, "Data").get("r", []))

    fields = [str(attributes(field).get("name", "")) for field in field_nodes]
    rows: list[list[str]] = []
    warnings: list[str] = []

    for row in row_nodes:
        cells = as_list(row.get("c", [])) if isinstance(row, dict) else []
        rows.append([_cell_text(cell) for cell in cells])

    expected_num_rows = _int_attribute(child(raw_config, "NumRows"), "value")
    if expected_num_rows is not None and expected_num_rows != len(rows):
        warnings.append(f"TextInput NumRows={expected_num_rows} but parsed {len(rows)} rows")

    for index, row in enumerate(rows, start=1):
        if fields and len(row) != len(fields):
            warnings.append(f"TextInput row {index} has {len(row)} cells for {len(fields)} fields")

    return ToolParserResult(
        normalized_config={
            "fields": fields,
            "rows": rows,
            "num_rows": expected_num_rows,
        },
        warnings=warnings,
    )


def _int_attribute(node: Any, name: str) -> int | None:
    raw_value = attributes(node).get(name)
    if raw_value in (None, ""):
        return None
    return int(raw_value)


def _cell_text(node: Any) -> str:
    if isinstance(node, dict) and not node:
        return ""
    return text(node, "")
