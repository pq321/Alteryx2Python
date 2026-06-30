from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, text


def parse_datetimenow_config(raw_config: dict[str, Any]) -> ToolParserResult:
    values = {
        str(attributes(value).get("name", "")): text(value)
        for value in as_list(raw_config.get("Value"))
        if attributes(value).get("name")
    }
    return ToolParserResult(
        normalized_config={
            "language": values.get("Language", "English"),
            "output_format": values.get("OutputFormat", "yyyy-MM-dd"),
        }
    )
