from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text
from alteryx2python.parser.tool_parsers.dbfileinput_parser import parse_dbfileinput_config


def parse_dynamicinput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    input_configuration = child(child(raw_config, "InputConfiguration"), "Configuration")
    return ToolParserResult(
        {
            "input_configuration": parse_dbfileinput_config(input_configuration).normalized_config,
            "mode": text(child(raw_config, "Mode"), ""),
            "read_list_field": text(child(raw_config, "ReadList_Field"), ""),
            "read_list_type": text(child(raw_config, "ReadList_Type"), ""),
            "modifications": child(raw_config, "Modifications"),
        }
    )
