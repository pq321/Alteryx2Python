from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, text


def parse_filter_config(raw_config: dict[str, Any]) -> ToolParserResult:
    normalized = {
        "expression": text(raw_config.get("Expression"), ""),
        "mode": text(raw_config.get("Mode"), "Unknown"),
    }
    return ToolParserResult(normalized_config=normalized)
