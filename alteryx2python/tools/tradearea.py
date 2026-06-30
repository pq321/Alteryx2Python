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
        raise KeyError("TradeArea tool requires an Input anchor")
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


def _parse_radius_specs(radii: str) -> list[tuple[str, float]]:
    specs: list[tuple[str, float]] = []
    for raw_part in str(radii or "").split(","):
        label = raw_part.strip()
        if not label:
            continue
        numeric_parts = [part for part in re.split(r"\s*-\s*", label) if part]
        try:
            radius = float(numeric_parts[-1])
        except (ValueError, IndexError):
            continue
        specs.append((label, radius))
    return specs


def _radius_to_degrees(radius: float, units: str) -> float:
    normalized = units.lower()
    if normalized.startswith("mile"):
        return radius / 69.0
    if normalized.startswith("kilometer"):
        return radius / 111.0
    if normalized.startswith("meter"):
        return radius / 111_000.0
    if normalized.startswith("minute"):
        return radius / 69.0
    return radius


def _circle_polygon(center: tuple[float, float] | None, radius: float, units: str, segments: int = 32) -> str | None:
    if center is None:
        return None
    cx, cy = center
    degree_radius = _radius_to_degrees(radius, units)
    points = []
    for index in range(segments):
        angle = 2 * math.pi * index / segments
        points.append((cx + degree_radius * math.cos(angle), cy + degree_radius * math.sin(angle)))
    points.append(points[0])
    ring = ", ".join(f"{x:.8g} {y:.8g}" for x, y in points)
    return f"POLYGON (({ring}))"


def tradearea_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    spatial_field = str(config.get("spatial_field", ""))
    ensure_fields_exist(input_frame, [spatial_field])

    if bool(config.get("radius_from_field", False)):
        raise NotImplementedError("TradeArea radius-from-field mode is not supported")

    units = str(config.get("units", ""))
    radius_specs = _parse_radius_specs(str(config.get("radii", "")))
    output_rows: list[dict[str, Any]] = []
    for _, row in input_frame.iterrows():
        base_row = row.to_dict()
        if not bool(config.get("include_source", True)):
            base_row.pop(spatial_field, None)
        center = _center(row[spatial_field])
        for label, radius in radius_specs:
            output_row = dict(base_row)
            output_row["SpatialObject_TradeArea"] = _circle_polygon(center, radius, units)
            output_row["RadiusSize"] = label
            output_rows.append(output_row)
    output = pd.DataFrame(output_rows)

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="TradeArea",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "spatial_field": spatial_field,
            "units": units,
            "no_overlap": bool(config.get("no_overlap", False)),
            "drive_time_dataset": config.get("drive_time_dataset", ""),
            "radii": [label for label, _radius in radius_specs],
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class TradeAreaTool(BaseTool):
    tool_type = "TradeArea"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return tradearea_tool(inputs, config, context)
