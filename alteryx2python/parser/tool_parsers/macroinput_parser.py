from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child
from alteryx2python.parser.tool_parsers.textinput_parser import parse_textinput_config


def parse_macroinput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    text_input_config = child(child(raw_config, "TextInput"), "Configuration")
    if not text_input_config:
        return ToolParserResult(
            normalized_config={},
            warnings=["MacroInput has no embedded TextInput configuration"],
        )

    parsed = parse_textinput_config(text_input_config)
    return ToolParserResult(
        normalized_config={
            **parsed.normalized_config,
            "source": "embedded_textinput",
        },
        warnings=parsed.warnings,
    )
