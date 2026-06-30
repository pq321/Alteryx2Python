from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def parse_spatialinfo_config(raw_config: dict[str, Any]) -> ToolParserResult:
    selected_items = [
        str(attributes(item).get("name", ""))
        for item in as_list(child(child(raw_config, "SelectedItems"), "Item"))
        if attributes(item).get("name")
    ]
    return ToolParserResult(
        normalized_config={
            "spatial_field": str(attributes(child(raw_config, "SpatialObj")).get("field", "")),
            "selected_items": selected_items,
        }
    )
