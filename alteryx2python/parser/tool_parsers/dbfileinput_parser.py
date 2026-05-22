from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def parse_dbfileinput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    file_node = child(raw_config, "File")
    normalized = {
        "file": text(file_node, ""),
        "file_attributes": attributes(file_node),
        "format_specific_options": child(raw_config, "FormatSpecificOptions"),
    }
    return ToolParserResult(normalized_config=normalized)
