from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def parse_dbfileoutput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    file_node = child(raw_config, "File")
    format_options = child(raw_config, "FormatSpecificOptions")
    normalized = {
        "file": text(file_node, ""),
        "file_attributes": attributes(file_node),
        "format_specific_options": format_options,
        "output_option": text(format_options.get("OutputOption"), ""),
    }
    return ToolParserResult(normalized_config=normalized)
