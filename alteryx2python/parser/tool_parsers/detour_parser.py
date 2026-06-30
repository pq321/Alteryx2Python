from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child


def parse_detour_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "detour_right": str(attributes(child(raw_config, "DetourRight")).get("value", "False")).lower()
            == "true"
        }
    )
