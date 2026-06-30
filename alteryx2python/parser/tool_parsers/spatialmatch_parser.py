from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child
from alteryx2python.parser.tool_parsers.select_parser import parse_select_config


def parse_spatialmatch_config(raw_config: dict[str, Any]) -> ToolParserResult:
    select_config = child(child(raw_config, "SelectConfiguration"), "Configuration")
    select_result = parse_select_config(select_config)
    return ToolParserResult(
        normalized_config={
            "target_spatial_field": str(attributes(child(raw_config, "Target")).get("SpatialObj", "")),
            "universe_spatial_field": str(attributes(child(raw_config, "Universe")).get("SpatialObj", "")),
            "method": str(attributes(child(raw_config, "Method")).get("method", "")),
            "intersect_poly": str(attributes(child(raw_config, "IntersectPoly")).get("value", "False")).lower() == "true",
            "select_fields": select_result.normalized_config["select_fields"],
        },
        warnings=select_result.warnings,
    )
