from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


_COORD_PAIR_RE = re.compile(r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")
_EARTH_RADIUS_MILES = 3958.7613


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("Distance tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _coordinates(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, str):
        return []
    return [(float(match.group(1)), float(match.group(2))) for match in _COORD_PAIR_RE.finditer(value)]


def _center(value: Any) -> tuple[float, float] | None:
    points = _coordinates(value)
    if not points:
        return None
    return sum(point[0] for point in points) / len(points), sum(point[1] for point in points) / len(points)


def _distance_miles(source: tuple[float, float] | None, destination: tuple[float, float] | None) -> float | None:
    if source is None or destination is None:
        return None
    lon1, lat1 = map(math.radians, source)
    lon2, lat2 = map(math.radians, destination)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(hav)))


def _convert_distance(miles: float | None, units: str) -> float | pd._libs.missing.NAType:
    if miles is None:
        return pd.NA
    normalized = units.lower()
    if normalized.startswith("kilometer"):
        return miles * 1.609344
    if normalized.startswith("meter"):
        return miles * 1609.344
    if normalized.startswith("feet") or normalized.startswith("foot"):
        return miles * 5280
    return miles


def _distance_field_name(units: str) -> str:
    normalized = units.lower()
    if normalized.startswith("kilometer"):
        return "DistanceKilometers"
    if normalized.startswith("meter"):
        return "DistanceMeters"
    if normalized.startswith("feet") or normalized.startswith("foot"):
        return "DistanceFeet"
    return "DistanceMiles"


def _bearing_degrees(source: tuple[float, float] | None, destination: tuple[float, float] | None) -> float | None:
    if source is None or destination is None:
        return None
    lon1, lat1 = map(math.radians, source)
    lon2, lat2 = map(math.radians, destination)
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _cardinal_direction(degrees: float | None) -> str | pd._libs.missing.NAType:
    if degrees is None:
        return pd.NA
    directions = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return directions[int((degrees + 22.5) // 45) % len(directions)]


def distance_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    source_field = str(config.get("source_spatial_field", ""))
    destination_field = str(config.get("destination_spatial_field", ""))
    ensure_fields_exist(input_frame, [source_field, destination_field])

    output = input_frame.copy()
    units = str(config.get("output_units", "Miles") or "Miles")
    sources = [_center(value) for value in output[source_field]]
    destinations = [_center(value) for value in output[destination_field]]
    distances_miles = [_distance_miles(source, destination) for source, destination in zip(sources, destinations, strict=False)]

    if bool(config.get("output_distance", False)):
        output[_distance_field_name(units)] = [_convert_distance(distance, units) for distance in distances_miles]

    if bool(config.get("output_drive_time_and_distance", False)):
        output[f"DriveDistance{_distance_field_name(units).removeprefix('Distance')}"] = [
            _convert_distance(distance, units) for distance in distances_miles
        ]
        output["DriveTimeMinutes"] = pd.NA

    bearings = [_bearing_degrees(source, destination) for source, destination in zip(sources, destinations, strict=False)]
    if bool(config.get("output_cardinal_direction", False)):
        output["Direction"] = [_cardinal_direction(degrees) for degrees in bearings]
    if bool(config.get("output_direction_degrees", False)):
        output["DirectionDegrees"] = [degrees if degrees is not None else pd.NA for degrees in bearings]

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Distance",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "source_spatial_field": source_field,
            "destination_spatial_field": destination_field,
            "output_units": units,
            "output_distance": bool(config.get("output_distance", False)),
            "output_drive_time_and_distance": bool(config.get("output_drive_time_and_distance", False)),
            "output_cardinal_direction": bool(config.get("output_cardinal_direction", False)),
            "output_direction_degrees": bool(config.get("output_direction_degrees", False)),
            "drive_time_dataset": config.get("drive_time_dataset", ""),
            "return_nearest": bool(config.get("return_nearest", False)),
            "distance_to_inside_edge": bool(config.get("distance_to_inside_edge", False)),
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DistanceTool(BaseTool):
    tool_type = "Distance"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return distance_tool(inputs, config, context)
