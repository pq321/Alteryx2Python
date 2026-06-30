from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _dataframe_inputs(inputs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {anchor: frame for anchor, frame in inputs.items() if isinstance(frame, pd.DataFrame)}


def _first_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    for frame in inputs.values():
        if isinstance(frame, pd.DataFrame):
            return frame
    return None


def baseline_tool(
    tool_type: str,
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
    default_output_anchors: tuple[str, ...] = ("Output",),
) -> dict[str, pd.DataFrame]:
    frame = _first_frame(inputs)
    output_anchors = tuple(str(anchor) for anchor in config.get("node_output_anchors", []) if anchor)
    if not output_anchors:
        output_anchors = default_output_anchors

    if frame is None:
        template = pd.DataFrame(
            [
                {
                    "tool_type": tool_type,
                    "baseline_semantics": "metadata_only",
                }
            ]
        )
    else:
        template = frame.copy()

    outputs = {anchor: template.copy() for anchor in output_anchors}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=tool_type,
        source_tool_id=config.get("source_tool_id"),
        inputs=_dataframe_inputs(inputs),
        outputs=outputs,
        status="success",
        config={
            "baseline_semantics": "passthrough_or_metadata_only",
            "node_input_anchors": config.get("node_input_anchors", []),
            "node_output_anchors": config.get("node_output_anchors", []),
            "input_schemas": {
                anchor: snapshot_schema(input_frame)
                for anchor, input_frame in inputs.items()
                if isinstance(input_frame, pd.DataFrame)
            },
            "output_schemas": {anchor: snapshot_schema(output) for anchor, output in outputs.items()},
        },
    )
    return outputs


class BaselineTool(BaseTool):
    tool_type = "Baseline"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        tool_type = str(config.get("tool_type", self.tool_type))
        return baseline_tool(tool_type, inputs, config, context)
