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
        raise KeyError("SpatialInfo tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _wkt_points(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, str):
        return []
    return [(float(match.group(1)), float(match.group(2))) for match in _COORD_PAIR_RE.finditer(value)]


def _is_polygon(value: Any) -> bool:
    return isinstance(value, str) and value.strip().upper().startswith(("POLYGON", "MULTIPOLYGON"))


def _format_point(point: tuple[float, float] | None) -> str | None:
    if point is None:
        return None
    return f"POINT ({point[0]:g} {point[1]:g})"


def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _polygon_area(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 3:
        return None
    ring = points
    if ring[0] != ring[-1]:
        ring = [*ring, ring[0]]
    area = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _centroid(points: list[tuple[float, float]], is_polygon: bool) -> tuple[float, float] | None:
    if not points:
        return None
    if is_polygon and len(points) >= 3:
        ring = points
        if ring[0] != ring[-1]:
            ring = [*ring, ring[0]]
        signed_area = 0.0
        cx = 0.0
        cy = 0.0
        for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
            cross = x1 * y2 - x2 * y1
            signed_area += cross
            cx += (x1 + x2) * cross
            cy += (y1 + y2) * cross
        signed_area *= 0.5
        if not math.isclose(signed_area, 0.0):
            return cx / (6 * signed_area), cy / (6 * signed_area)
    return sum(point[0] for point in points) / len(points), sum(point[1] for point in points) / len(points)


def _rect_polygon(bounds: tuple[float, float, float, float] | None) -> str | None:
    if bounds is None:
        return None
    min_x, min_y, max_x, max_y = bounds
    return (
        f"POLYGON (({min_x:g} {max_y:g}, {max_x:g} {max_y:g}, "
        f"{max_x:g} {min_y:g}, {min_x:g} {min_y:g}, {min_x:g} {max_y:g}))"
    )


def _series_apply(
    frame: pd.DataFrame,
    spatial_field: str,
    func,
) -> list[Any]:
    return [func(value, _wkt_points(value)) for value in frame[spatial_field]]


def spatialinfo_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    spatial_field = str(config.get("spatial_field", ""))
    selected_items = list(config.get("selected_items", []) or [])
    ensure_fields_exist(input_frame, [spatial_field])

    output = input_frame.copy()
    if "AreaMi" in selected_items:
        output["AreaSqMi"] = _series_apply(
            output,
            spatial_field,
            lambda value, points: _polygon_area(points) if _is_polygon(value) else pd.NA,
        )
    if "CentroidObj" in selected_items or "CentroidXY" in selected_items:
        centroids = _series_apply(
            output,
            spatial_field,
            lambda value, points: _centroid(points, _is_polygon(value)),
        )
        if "CentroidObj" in selected_items:
            output["Centroid"] = [_format_point(point) for point in centroids]
        if "CentroidXY" in selected_items:
            output["CentroidX"] = [point[0] if point is not None else pd.NA for point in centroids]
            output["CentroidY"] = [point[1] if point is not None else pd.NA for point in centroids]
    if "RectObj" in selected_items or "RectPolygon" in selected_items or "RectXY" in selected_items:
        bounds = _series_apply(output, spatial_field, lambda _value, points: _bbox(points))
        if "RectObj" in selected_items:
            output["BoundingRect_TopLeft"] = [
                _format_point((bound[0], bound[3])) if bound is not None else None for bound in bounds
            ]
            output["BoundingRect_BottomRight"] = [
                _format_point((bound[2], bound[1])) if bound is not None else None for bound in bounds
            ]
        if "RectPolygon" in selected_items:
            output["BoundingRect"] = [_rect_polygon(bound) for bound in bounds]
        if "RectXY" in selected_items:
            output["BR_TopLeft_X"] = [bound[0] if bound is not None else pd.NA for bound in bounds]
            output["BR_TopLeft_Y"] = [bound[3] if bound is not None else pd.NA for bound in bounds]
            output["BR_BottomRight_X"] = [bound[2] if bound is not None else pd.NA for bound in bounds]
            output["BR_BottomRight_Y"] = [bound[1] if bound is not None else pd.NA for bound in bounds]
    if "EndPointsObj" in selected_items or "EndPointsXY" in selected_items:
        endpoints = _series_apply(
            output,
            spatial_field,
            lambda _value, points: (points[0], points[-1]) if points else (None, None),
        )
        if "EndPointsObj" in selected_items:
            output["StartPoint"] = [_format_point(start) for start, _end in endpoints]
            output["EndPoint"] = [_format_point(end) for _start, end in endpoints]
        if "EndPointsXY" in selected_items:
            output["StartPoint_X"] = [start[0] if start is not None else pd.NA for start, _end in endpoints]
            output["StartPoint_Y"] = [start[1] if start is not None else pd.NA for start, _end in endpoints]
            output["EndPoint_X"] = [end[0] if end is not None else pd.NA for _start, end in endpoints]
            output["EndPoint_Y"] = [end[1] if end is not None else pd.NA for _start, end in endpoints]

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="SpatialInfo",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "spatial_field": spatial_field,
            "selected_items": selected_items,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class SpatialInfoTool(BaseTool):
    tool_type = "SpatialInfo"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return spatialinfo_tool(inputs, config, context)
