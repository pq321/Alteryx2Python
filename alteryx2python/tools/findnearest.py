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


def _frame(inputs: dict[str, pd.DataFrame], anchor: str) -> pd.DataFrame:
    if anchor not in inputs:
        raise KeyError(f"FindNearest tool requires a {anchor} anchor")
    frame = inputs[anchor]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{anchor} anchor must contain a pandas DataFrame")
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


def _convert_distance(miles: float, units: str) -> float:
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


def _prefixed_row(row: pd.Series, prefix: str) -> dict[str, Any]:
    return {f"{prefix}_{column}": row[column] for column in row.index}


def _selected_output(joined: pd.DataFrame, select_fields: list[dict[str, Any]]) -> pd.DataFrame:
    if not select_fields:
        return joined
    explicit_sources = {str(field.get("source", "")) for field in select_fields if field.get("source") != "*Unknown"}
    output_columns: dict[str, pd.Series] = {}
    for field in select_fields:
        if not field.get("selected", True):
            continue
        source = str(field.get("source", ""))
        if source == "*Unknown":
            for column in joined.columns:
                if column not in explicit_sources and column not in output_columns:
                    output_columns[column] = joined[column].copy()
            continue
        if source not in joined.columns:
            continue
        rename = str(field.get("rename", source))
        output_columns[rename] = joined[source].copy()
    return pd.DataFrame(output_columns, index=joined.index)


def findnearest_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    targets = _frame(inputs, "Targets")
    universe = _frame(inputs, "Universe")
    target_spatial_field = str(config.get("target_spatial_field", ""))
    universe_spatial_field = str(config.get("universe_spatial_field", ""))
    ensure_fields_exist(targets, [target_spatial_field])
    ensure_fields_exist(universe, [universe_spatial_field])

    units = str(config.get("max_distance_units", "Miles") or "Miles")
    distance_field = _distance_field_name(units)
    max_distance = float(config.get("max_distance", 0.0) or 0.0)
    how_many = max(1, int(config.get("how_many", 1) or 1))
    ignore_zero_distance = bool(config.get("ignore_zero_distance", False))

    target_centers = [_center(value) for value in targets[target_spatial_field]]
    universe_centers = [_center(value) for value in universe[universe_spatial_field]]
    rows: list[dict[str, Any]] = []
    for target_position, target_row in enumerate(targets.itertuples(index=False, name=None)):
        target_series = pd.Series(target_row, index=targets.columns)
        ranked_candidates: list[tuple[float, int, pd.Series]] = []
        for universe_position, universe_row in enumerate(universe.itertuples(index=False, name=None)):
            universe_series = pd.Series(universe_row, index=universe.columns)
            distance_miles = _distance_miles(target_centers[target_position], universe_centers[universe_position])
            if distance_miles is None:
                continue
            distance = _convert_distance(distance_miles, units)
            if ignore_zero_distance and math.isclose(distance, 0.0):
                continue
            if max_distance > 0 and not units.lower().startswith("drive") and distance > max_distance:
                continue
            ranked_candidates.append((distance, universe_position, universe_series))

        ranked_candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
        for rank, (distance, _universe_position, universe_series) in enumerate(ranked_candidates[:how_many], start=1):
            bearing = _bearing_degrees(target_centers[target_position], _center(universe_series[universe_spatial_field]))
            rows.append(
                {
                    **_prefixed_row(target_series, "Target"),
                    **_prefixed_row(universe_series, "Universe"),
                    "FindNearestRank": rank,
                    distance_field: distance,
                    "Direction": _cardinal_direction(bearing),
                }
            )

    joined = pd.DataFrame(rows)
    select_fields = [field for field in config.get("select_fields", []) if isinstance(field, dict)]
    output = _selected_output(joined, select_fields).reset_index(drop=True)
    outputs = {"Matched": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="FindNearest",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Targets": targets, "Universe": universe},
        outputs=outputs,
        status="success",
        config={
            "target_spatial_field": target_spatial_field,
            "universe_spatial_field": universe_spatial_field,
            "how_many": how_many,
            "max_distance": max_distance,
            "max_distance_units": units,
            "ignore_zero_distance": ignore_zero_distance,
            "universe_file": config.get("universe_file", ""),
            "input_schema": {"Targets": snapshot_schema(targets), "Universe": snapshot_schema(universe)},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class FindNearestTool(BaseTool):
    tool_type = "FindNearest"
    input_anchors = ("Targets", "Universe")
    output_anchors = ("Matched",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return findnearest_tool(inputs, config, context)
