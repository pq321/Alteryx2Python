from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def _bool_attr(node: Any, name: str, default: bool = False) -> bool:
    value = attributes(node).get(name)
    if value is None:
        return default
    return str(value).lower() == "true"


def parse_distance_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "source_spatial_field": text(child(raw_config, "SpatialObjSource"), ""),
            "destination_spatial_field": text(child(raw_config, "SpatialObjDest"), ""),
            "output_distance": _bool_attr(child(raw_config, "OutputDistance"), "value", False),
            "return_nearest": _bool_attr(child(raw_config, "ReturnNearest"), "value", False),
            "distance_to_inside_edge": _bool_attr(child(raw_config, "DistToInsideEdge"), "value", False),
            "output_drive_time_and_distance": _bool_attr(
                child(raw_config, "OutputDriveTimeAndDistance"),
                "value",
                False,
            ),
            "drive_time_dataset": text(child(raw_config, "DriveTimeDataSet"), ""),
            "allow_reverse_route": _bool_attr(child(raw_config, "AllowReverseRoute"), "value", False),
            "output_cardinal_direction": _bool_attr(child(raw_config, "OutputCardinalDirection"), "value", False),
            "output_direction_degrees": _bool_attr(child(raw_config, "OutputDirectionDegrees"), "value", False),
            "is_metric": _bool_attr(child(raw_config, "IsMetric"), "value", False),
            "output_units": text(child(raw_config, "OutputUnits"), ""),
        }
    )
