from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def parse_dynamicinput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    input_configuration = child(child(raw_config, "InputConfiguration"), "Configuration")
    return ToolParserResult(
        {
            "input_configuration": input_configuration,
            "mode": text(child(raw_config, "Mode"), ""),
            "modifications": child(raw_config, "Modifications"),
        }
    )
