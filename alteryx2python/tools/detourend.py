from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _frames(inputs: dict[str, pd.DataFrame]) -> list[pd.DataFrame]:
    frames = [frame for anchor, frame in sorted(inputs.items()) if anchor in {"Left", "Right"} and isinstance(frame, pd.DataFrame)]
    if not frames:
        raise KeyError("DetourEnd tool requires a Left or Right anchor")
    return frames


def detourend_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    frames = _frames(inputs)
    output = pd.concat(frames, ignore_index=True, sort=False)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DetourEnd",
        source_tool_id=config.get("source_tool_id"),
        inputs={key: frame for key, frame in inputs.items() if isinstance(frame, pd.DataFrame)},
        outputs=outputs,
        status="success",
        config={
            "input_schemas": {
                anchor: snapshot_schema(frame) for anchor, frame in inputs.items() if isinstance(frame, pd.DataFrame)
            },
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DetourEndTool(BaseTool):
    tool_type = "DetourEnd"
    input_anchors = ("Left", "Right")
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return detourend_tool(inputs, config, context)
