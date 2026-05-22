from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, text


def parse_recordid_config(raw_config: dict[str, Any]) -> ToolParserResult:
    normalized = {
        "field_name": text(raw_config.get("FieldName"), "RecordID"),
        "start_value": int(text(raw_config.get("StartValue"), "1")),
        "field_type": text(raw_config.get("FieldType"), "Int32"),
        "field_size": int(text(raw_config.get("FieldSize"), "6")),
        "position": int(text(raw_config.get("Position"), "0")),
    }
    return ToolParserResult(normalized_config=normalized)
