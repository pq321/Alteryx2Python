from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult


def parse_expectequal_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(normalized_config={})
