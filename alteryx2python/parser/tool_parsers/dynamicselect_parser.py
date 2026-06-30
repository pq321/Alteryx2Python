from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def _text_or_empty(node: Any) -> str:
    value = text(node, "")
    return "" if value == "{}" else value


def parse_dynamicselect_config(raw_config: dict[str, Any]) -> ToolParserResult:
    field_types = [
        value.strip()
        for value in _text_or_empty(child(raw_config, "FieldTypes")).split(",")
        if value.strip()
    ]
    normalized = {
        "mode": _text_or_empty(child(raw_config, "Mode")),
        "field_types": field_types,
        "expression": _text_or_empty(child(raw_config, "Expression")),
    }
    return ToolParserResult(normalized_config=normalized)
