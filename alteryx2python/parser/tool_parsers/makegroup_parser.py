from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def parse_makegroup_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "key_first": text(child(raw_config, "Key1st"), ""),
            "key_second": text(child(raw_config, "Key2nd"), ""),
        }
    )
