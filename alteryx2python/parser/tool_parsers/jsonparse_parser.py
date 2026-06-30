from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, text


def parse_jsonparse_config(raw_config: dict[str, Any]) -> ToolParserResult:
    normalized = {
        "json_field": text(raw_config.get("JSON_Field"), ""),
        "include_in_output": str(raw_config.get("IncludeInOutput", {}).get("attributes", {}).get("value", "False")).lower() == "true",
        "single_field": str(raw_config.get("SingleField", {}).get("attributes", {}).get("value", "False")).lower() == "true",
    }
    return ToolParserResult(normalized_config=normalized)
