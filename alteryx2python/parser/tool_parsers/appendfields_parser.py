from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, text, child
from alteryx2python.parser.tool_parsers.select_parser import parse_select_config


def parse_appendfields_config(raw_config: dict[str, Any]) -> ToolParserResult:
    config = {"cartesian_mode": text(raw_config.get("CartesianMode"), "Error")}
    if raw_config.get("SelectConfiguration"):
        selection = child(child(raw_config, "SelectConfiguration"), "Configuration")
        config.update(parse_select_config(selection, default_rename=False).normalized_config)
    return ToolParserResult(normalized_config=config)
