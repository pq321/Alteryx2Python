from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, text


def parse_datetime_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "is_from": str(attributes(raw_config.get("IsFrom", {})).get("value", "False")).lower() == "true",
            "input_field_name": text(raw_config.get("InputFieldName")),
            "language": text(raw_config.get("Language"), "English"),
            "format": text(raw_config.get("Format")),
            "output_field_name": text(raw_config.get("OutputFieldName")),
        }
    )
