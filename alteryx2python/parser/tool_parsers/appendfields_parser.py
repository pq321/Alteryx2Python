from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, text


def parse_appendfields_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "cartesian_mode": text(raw_config.get("CartesianMode"), "Error"),
        }
    )
