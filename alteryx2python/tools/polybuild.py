from __future__ import annotations

import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


_COORD_PAIR_RE = re.compile(r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("PolyBuild tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _coordinates(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, str):
        return []
    return [(float(match.group(1)), float(match.group(2))) for match in _COORD_PAIR_RE.finditer(value)]


def _first_coordinate(value: Any) -> tuple[float, float] | None:
    points = _coordinates(value)
    if not points:
        return None
    return points[0]


def _cross(origin: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])


def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    unique_points = sorted(set(points))
    if len(unique_points) <= 1:
        return unique_points
    lower: list[tuple[float, float]] = []
    for point in unique_points:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique_points):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _polygon(points: list[tuple[float, float]]) -> str | None:
    if len(points) < 3:
        return None
    ring = points
    if ring[0] != ring[-1]:
        ring = [*ring, ring[0]]
    return "POLYGON ((" + ", ".join(f"{x:g} {y:g}" for x, y in ring) + "))"


def polybuild_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    spatial_field = str(config.get("spatial_field", ""))
    group_field = str(config.get("group_field", ""))
    sequence_field = str(config.get("sequence_field", ""))
    required_fields = [spatial_field]
    if group_field:
        required_fields.append(group_field)
    if sequence_field:
        required_fields.append(sequence_field)
    ensure_fields_exist(input_frame, required_fields)

    build_type = str(config.get("build_type", "") or "")
    group_keys = [group_field] if group_field else []
    grouped = input_frame.groupby(group_keys, dropna=False, sort=False) if group_keys else [(None, input_frame)]
    rows: list[dict[str, Any]] = []
    for group_value, group in grouped:
        working = group.sort_values(sequence_field, kind="stable") if sequence_field else group
        points = [point for point in (_first_coordinate(value) for value in working[spatial_field]) if point is not None]
        if build_type.lower() == "convexhull":
            points = _convex_hull(points)
        row: dict[str, Any] = {}
        if group_field:
            row[group_field] = group_value[0] if isinstance(group_value, tuple) and len(group_value) == 1 else group_value
        row["SpatialObj_Built"] = _polygon(points)
        rows.append(row)

    output = pd.DataFrame(rows)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="PolyBuild",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "spatial_field": spatial_field,
            "group_field": group_field,
            "build_type": build_type,
            "sequence_field": sequence_field,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class PolyBuildTool(BaseTool):
    tool_type = "PolyBuild"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return polybuild_tool(inputs, config, context)
