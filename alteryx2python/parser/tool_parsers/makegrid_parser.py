from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def _bool_attr(raw_config: dict[str, Any], key: str) -> bool:
    return str(attributes(child(raw_config, key)).get("value", "False")).lower() == "true"


def parse_makegrid_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "spatial_field": text(child(raw_config, "SpatialObjIn"), ""),
            "grid_size": attributes(child(raw_config, "GridSize")).get("value", ""),
            "units": text(child(raw_config, "Units"), ""),
            "grid_per_object": _bool_attr(raw_config, "GridPerObject"),
            "clip_to_poly": _bool_attr(raw_config, "ClipToPoly"),
        }
    )
