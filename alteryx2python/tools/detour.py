from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("Detour tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def detour_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    detour_right = bool(config.get("detour_right", False))
    active = input_frame.copy()
    inactive = input_frame.iloc[0:0].copy()
    outputs = {"Left": inactive if detour_right else active, "Right": active if detour_right else inactive}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Detour",
        source_tool_id=config.get("source_tool_id"),
        inputs={key: frame for key, frame in inputs.items() if isinstance(frame, pd.DataFrame)},
        outputs=outputs,
        status="success",
        config={
            "detour_right": detour_right,
            "input_schema": snapshot_schema(input_frame),
            "output_schemas": {anchor: snapshot_schema(frame) for anchor, frame in outputs.items()},
        },
    )
    return outputs


class DetourTool(BaseTool):
    tool_type = "Detour"
    input_anchors = ("Input", "Action")
    output_anchors = ("Left", "Right")

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return detour_tool(inputs, config, context)
