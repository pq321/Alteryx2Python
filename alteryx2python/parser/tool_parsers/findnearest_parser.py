from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text
from alteryx2python.parser.tool_parsers.select_parser import parse_select_config


def _bool_attr(node: Any, name: str, default: bool = False) -> bool:
    value = attributes(node).get(name)
    if value is None:
        return default
    return str(value).lower() == "true"


def _int_attr(node: Any, name: str, default: int) -> int:
    try:
        return int(attributes(node).get(name, default))
    except (TypeError, ValueError):
        return default


def _float_attr(node: Any, name: str, default: float) -> float:
    try:
        return float(attributes(node).get(name, default))
    except (TypeError, ValueError):
        return default


def parse_findnearest_config(raw_config: dict[str, Any]) -> ToolParserResult:
    select_config = child(child(raw_config, "SelectConfiguration"), "Configuration")
    select_result = parse_select_config(select_config)
    universe = child(raw_config, "Universe")
    return ToolParserResult(
        normalized_config={
            "target_spatial_field": str(attributes(child(raw_config, "Target")).get("SpatialObj", "")),
            "universe_spatial_field": str(attributes(universe).get("SpatialObj", "")),
            "how_many": _int_attr(child(raw_config, "HowMany"), "value", 1),
            "max_distance": _float_attr(child(raw_config, "MaxDistance"), "value", 0.0),
            "max_distance_units": text(child(raw_config, "MaxDistanceUnits"), "Miles"),
            "ignore_zero_distance": _bool_attr(child(raw_config, "Ignore0"), "value", False),
            "drive_time_dataset": text(child(raw_config, "DriveTimeDataSet"), ""),
            "universe_file": text(child(universe, "File"), ""),
            "select_fields": select_result.normalized_config["select_fields"],
        },
        warnings=select_result.warnings,
    )
