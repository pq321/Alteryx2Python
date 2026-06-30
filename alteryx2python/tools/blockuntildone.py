from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def blockuntildone_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("BlockUntilDone tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    outputs = {
        "Output": input_frame.copy(),
        "Output2": input_frame.copy(),
        "Output3": input_frame.copy(),
    }
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="BlockUntilDone",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(input_frame),
        },
    )
    return outputs


class BlockUntilDoneTool(BaseTool):
    tool_type = "BlockUntilDone"
    input_anchors = ("Input",)
    output_anchors = ("Output", "Output2", "Output3")

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return blockuntildone_tool(inputs, config, context)
