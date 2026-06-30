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
        raise KeyError("PolySplit tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _points(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, str):
        return []
    return [(float(match.group(1)), float(match.group(2))) for match in _COORD_PAIR_RE.finditer(value)]


def _format_number(value: float) -> str:
    return f"{value:g}"


def _point_wkt(point: tuple[float, float]) -> str:
    return f"POINT ({_format_number(point[0])} {_format_number(point[1])})"


def polysplit_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    spatial_field = str(config.get("spatial_field", ""))
    split_to = str(config.get("split_to", "Point") or "Point")
    ensure_fields_exist(input_frame, [spatial_field])

    rows: list[dict[str, Any]] = []
    for original_index, row in input_frame.reset_index(drop=True).iterrows():
        for sequence, point in enumerate(_points(row[spatial_field]), start=1):
            output_row = row.to_dict()
            output_row["Split_SequenceNum"] = sequence
            output_row["Split_SpatialObj"] = _point_wkt(point) if split_to.lower() == "point" else row[spatial_field]
            output_row["Split_OriginalRecordID"] = original_index + 1
            rows.append(output_row)

    output = pd.DataFrame(rows, columns=[*input_frame.columns, "Split_SequenceNum", "Split_SpatialObj", "Split_OriginalRecordID"])
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="PolySplit",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "spatial_field": spatial_field,
            "split_to": split_to,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class PolySplitTool(BaseTool):
    tool_type = "PolySplit"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return polysplit_tool(inputs, config, context)
