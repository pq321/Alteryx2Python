from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


_COORD_PAIR_RE = re.compile(r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("Buffer tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _coordinates(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, str):
        return []
    return [(float(match.group(1)), float(match.group(2))) for match in _COORD_PAIR_RE.finditer(value)]


def _radius_to_degrees(radius: float, units: str) -> float:
    normalized = units.lower()
    if normalized.startswith("mile"):
        return radius / 69.0
    if normalized.startswith("kilometer"):
        return radius / 111.0
    if normalized.startswith("meter"):
        return radius / 111_000.0
    if normalized.startswith("feet") or normalized.startswith("foot"):
        return radius / 364_000.0
    return radius


def _rect_polygon(points: list[tuple[float, float]], degree_radius: float) -> str | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = min(xs) - degree_radius
    min_y = min(ys) - degree_radius
    max_x = max(xs) + degree_radius
    max_y = max(ys) + degree_radius
    if min_x > max_x or min_y > max_y:
        return None
    return (
        f"POLYGON (({min_x:g} {max_y:g}, {max_x:g} {max_y:g}, "
        f"{max_x:g} {min_y:g}, {min_x:g} {min_y:g}, {min_x:g} {max_y:g}))"
    )


def _circle_polygon(center: tuple[float, float], degree_radius: float, segments: int = 32) -> str | None:
    if degree_radius < 0:
        return None
    cx, cy = center
    points = []
    for index in range(segments):
        angle = 2 * math.pi * index / segments
        points.append((cx + degree_radius * math.cos(angle), cy + degree_radius * math.sin(angle)))
    points.append(points[0])
    return "POLYGON ((" + ", ".join(f"{x:.8g} {y:.8g}" for x, y in points) + "))"


def _buffer_wkt(value: Any, radius: float, units: str) -> str | None:
    points = _coordinates(value)
    if not points:
        return None
    degree_radius = _radius_to_degrees(radius, units)
    if len(points) == 1:
        return _circle_polygon(points[0], degree_radius)
    return _rect_polygon(points, degree_radius)


def _row_radius(row: pd.Series, config: dict[str, Any]) -> float:
    if str(config.get("buffer_size_source", "")).lower() == "field":
        return float(row[str(config.get("buffer_size_field", ""))])
    return float(config.get("buffer_size", 0) or 0)


def buffer_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    spatial_field = str(config.get("spatial_field", ""))
    required_fields = [spatial_field]
    if str(config.get("buffer_size_source", "")).lower() == "field":
        required_fields.append(str(config.get("buffer_size_field", "")))
    ensure_fields_exist(input_frame, required_fields)

    units = str(config.get("units", "") or "Miles")
    include_source = bool(config.get("include_source", True))
    output_rows: list[dict[str, Any]] = []
    for _, row in input_frame.iterrows():
        output_row = row.to_dict() if include_source else {column: row[column] for column in input_frame.columns if column != spatial_field}
        output_row["SpatialObj_Buffer"] = _buffer_wkt(row[spatial_field], _row_radius(row, config), units)
        output_rows.append(output_row)
    output = pd.DataFrame(output_rows)

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Buffer",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "spatial_field": spatial_field,
            "include_source": include_source,
            "buffer_size_source": config.get("buffer_size_source", ""),
            "buffer_size": config.get("buffer_size", ""),
            "buffer_size_field": config.get("buffer_size_field", ""),
            "units": units,
            "generalize_to_one_percent": bool(config.get("generalize_to_one_percent", False)),
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class BufferTool(BaseTool):
    tool_type = "Buffer"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return buffer_tool(inputs, config, context)
