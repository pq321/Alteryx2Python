from __future__ import annotations

import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


_COORD_PAIR_RE = re.compile(r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")


def _points(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, str):
        return []
    return [(float(match.group(1)), float(match.group(2))) for match in _COORD_PAIR_RE.finditer(value)]


def _format(value: float) -> str:
    return f"{value:g}"


def _bbox_polygon(value: Any) -> str:
    points = _points(value)
    if not points:
        return "" if pd.isna(value) else str(value)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return (
        f"POLYGON (({_format(min_x)} {_format(max_y)}, {_format(max_x)} {_format(max_y)}, "
        f"{_format(max_x)} {_format(min_y)}, {_format(min_x)} {_format(min_y)}, {_format(min_x)} {_format(max_y)}))"
    )


def makegrid_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("MakeGrid tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    spatial_field = str(config.get("spatial_field", ""))
    ensure_fields_exist(input_frame, [spatial_field])

    output = input_frame.copy()
    output["Grid"] = [_bbox_polygon(value) for value in output[spatial_field]]
    output["GridSize"] = config.get("grid_size", "")
    output["GridUnits"] = config.get("units", "")
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="MakeGrid",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "spatial_field": spatial_field,
            "grid_size": config.get("grid_size", ""),
            "units": config.get("units", ""),
            "grid_per_object": bool(config.get("grid_per_object", False)),
            "clip_to_poly": bool(config.get("clip_to_poly", False)),
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class MakeGridTool(BaseTool):
    tool_type = "MakeGrid"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return makegrid_tool(inputs, config, context)
