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
        raise KeyError("Smooth tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _passes(value: Any) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _smooth_points(points: list[tuple[float, float]], passes: int) -> list[tuple[float, float]]:
    if len(points) < 3 or passes <= 0:
        return points
    closed = points[0] == points[-1]
    current = list(points)
    for _ in range(passes):
        next_points = [current[0]]
        last_inner_index = len(current) - 1 if closed else len(current) - 1
        for index in range(1, last_inner_index):
            prev_x, prev_y = current[index - 1]
            cur_x, cur_y = current[index]
            next_x, next_y = current[index + 1]
            next_points.append(((prev_x + cur_x + next_x) / 3, (prev_y + cur_y + next_y) / 3))
        if closed:
            next_points.append(current[-1])
        else:
            next_points.append(current[-1])
        current = next_points
    return current


def _replace_coordinate_pairs(value: Any, passes: int) -> Any:
    if not isinstance(value, str):
        return value
    matches = list(_COORD_PAIR_RE.finditer(value))
    if not matches:
        return value
    points = [(float(match.group(1)), float(match.group(2))) for match in matches]
    smoothed = _smooth_points(points, passes)
    pieces: list[str] = []
    last_end = 0
    for match, point in zip(matches, smoothed, strict=True):
        pieces.append(value[last_end : match.start()])
        pieces.append(f"{point[0]:g} {point[1]:g}")
        last_end = match.end()
    pieces.append(value[last_end:])
    return "".join(pieces)


def smooth_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    spatial_field = str(config.get("spatial_field", ""))
    ensure_fields_exist(input_frame, [spatial_field])

    output_field = str(config.get("output_field", "") or "SpatialObj_Smooth")
    include_source = bool(config.get("include_source", True))
    passes = _passes(config.get("passes", 0))
    output = input_frame.copy() if include_source else input_frame.drop(columns=[spatial_field]).copy()
    output[output_field] = [_replace_coordinate_pairs(value, passes) for value in input_frame[spatial_field]]

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Smooth",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "spatial_field": spatial_field,
            "output_field": output_field,
            "include_source": include_source,
            "passes": passes,
            "maximum_radius": config.get("maximum_radius", ""),
            "units": config.get("units", ""),
            "post_generalize": bool(config.get("post_generalize", False)),
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class SmoothTool(BaseTool):
    tool_type = "Smooth"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return smooth_tool(inputs, config, context)
