from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def _bool_attr(node: Any, name: str, default: bool = False) -> bool:
    value = attributes(node).get(name)
    if value is None:
        return default
    return str(value).lower() == "true"


def _optional_text(raw_config: dict[str, Any], key: str) -> str:
    value = raw_config.get(key)
    if value is None:
        return ""
    return text(value, "")


def parse_tradearea_config(raw_config: dict[str, Any]) -> ToolParserResult:
    spatial_obj = child(raw_config, "SpatialObj")
    units = child(raw_config, "Units")
    radius_from_field = child(raw_config, "Radius_FromField")
    return ToolParserResult(
        normalized_config={
            "spatial_field": str(attributes(spatial_obj).get("field", "")),
            "include_source": _bool_attr(spatial_obj, "includeOut", True),
            "units": str(attributes(units).get("units", "")),
            "no_overlap": _bool_attr(units, "noOverlap", False),
            "radius_from_field": _bool_attr(radius_from_field, "value", False),
            "radii": text(child(raw_config, "Radii"), ""),
            "drive_time_dataset": _optional_text(raw_config, "DriveTimeDataSet"),
        }
    )
