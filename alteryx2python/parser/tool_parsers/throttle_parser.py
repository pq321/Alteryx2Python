from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def parse_throttle_config(raw_config: dict[str, Any]) -> ToolParserResult:
    records_per_minute = text(child(raw_config, "RecordsPerMinute"), "")
    return ToolParserResult(normalized_config={"records_per_minute": records_per_minute})
