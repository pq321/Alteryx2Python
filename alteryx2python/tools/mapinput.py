from __future__ import annotations

import json
from typing import Any

import pandas as pd

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _format_coord(coord: Any) -> str:
    if isinstance(coord, float):
        return f"{coord:.15g}"
    return str(coord)


def _point_wkt(coordinates: list[Any]) -> str:
    if len(coordinates) < 2:
        return ""
    return f"POINT ({_format_coord(coordinates[0])} {_format_coord(coordinates[1])})"


def _ring_wkt(ring: list[Any]) -> str:
    return ", ".join(_point_pair_wkt(point) for point in ring)


def _point_pair_wkt(point: Any) -> str:
    if not isinstance(point, list) or len(point) < 2:
        return ""
    return f"{_format_coord(point[0])} {_format_coord(point[1])}"


def _polygon_wkt(coordinates: list[Any]) -> str:
    rings = [ring for ring in coordinates if isinstance(ring, list)]
    return f"POLYGON ({', '.join(f'({_ring_wkt(ring)})' for ring in rings)})"


def _geojson_to_wkt(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return str(value or "")
    try:
        geometry = json.loads(value)
    except json.JSONDecodeError:
        return value
    geometry_type = str(geometry.get("type", "")).lower()
    coordinates = geometry.get("coordinates")
    if geometry_type == "point" and isinstance(coordinates, list):
        return _point_wkt(coordinates)
    if geometry_type == "polygon" and isinstance(coordinates, list):
        return _polygon_wkt(coordinates)
    return value


def _mapinput_frame(config: dict[str, Any]) -> pd.DataFrame:
    rows = list(config.get("rows", []) or [])
    fields = list(config.get("fields", []) or [])
    if not rows:
        return pd.DataFrame(columns=fields)
    frame = pd.DataFrame(rows, columns=fields)
    if "SpatialObj" in frame.columns:
        frame["SpatialObj"] = frame["SpatialObj"].map(_geojson_to_wkt)
    return frame


def mapinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    output = _mapinput_frame(config)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="MapInput",
        source_tool_id=config.get("source_tool_id"),
        inputs={},
        outputs=outputs,
        status="success",
        config={
            "mode": config.get("mode", ""),
            "reference_file": config.get("reference_file", ""),
            "base_map": config.get("base_map", ""),
            "label_field": config.get("label_field", ""),
            "row_count": len(output.index),
        },
    )
    return outputs


class MapInputTool(BaseTool):
    tool_type = "MapInput"
    input_anchors = ()
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return mapinput_tool(inputs, config, context)
