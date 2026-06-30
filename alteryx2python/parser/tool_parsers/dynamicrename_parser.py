from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, text


def parse_dynamicrename_config(raw_config: dict[str, Any]) -> ToolParserResult:
    normalized = {
        "rename_mode": text(raw_config.get("RenameMode"), ""),
        "expression": text(raw_config.get("Expression"), ""),
    }
    return ToolParserResult(normalized_config=normalized)
