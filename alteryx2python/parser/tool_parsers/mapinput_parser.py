from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def _field_names(raw_config: dict[str, Any]) -> list[str]:
    return [
        str(attributes(field).get("name"))
        for field in as_list(child(child(raw_config, "Fields"), "Field"))
        if attributes(field).get("name")
    ]


def _rows(raw_config: dict[str, Any], fields: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in as_list(child(child(raw_config, "Data"), "r")):
        if attributes(row).get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true":
            continue
        cells = [text(cell) for cell in as_list(child(row, "c"))]
        if not cells:
            continue
        rows.append({field: cells[index] if index < len(cells) else "" for index, field in enumerate(fields)})
    return rows


def parse_mapinput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    fields = _field_names(raw_config)
    return ToolParserResult(
        normalized_config={
            "mode": text(child(raw_config, "Mode"), ""),
            "reference_file": text(child(raw_config, "ReferenceFile"), ""),
            "base_map": text(child(raw_config, "BaseMap"), ""),
            "label_field": text(child(raw_config, "ReferenceFileLabelField"), ""),
            "selection_stack": text(child(raw_config, "SelectionStack"), ""),
            "fields": fields,
            "rows": _rows(raw_config, fields),
        }
    )
