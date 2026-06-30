from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child


def parse_polysplit_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "spatial_field": str(attributes(child(raw_config, "SpatialObj")).get("field", "")),
            "split_to": str(attributes(child(raw_config, "SplitTo")).get("type", "")),
        }
    )
