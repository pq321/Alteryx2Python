from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def parse_union_config(raw_config: dict[str, Any]) -> ToolParserResult:
    normalized = {
        "mode": text(raw_config.get("Mode"), "Unknown"),
        "by_name_error_mode": text(raw_config.get("ByName_ErrorMode"), ""),
        "by_name_output_mode": text(raw_config.get("ByName_OutputMode"), ""),
        "set_output_order": str(attributes(raw_config.get("SetOutputOrder", {})).get("value", "False")).lower() == "true",
    }
    return ToolParserResult(normalized_config=normalized)
