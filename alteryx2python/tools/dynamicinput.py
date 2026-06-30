from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def dynamicinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = inputs.get("Input")
    if input_frame is not None and not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    output = input_frame.copy() if isinstance(input_frame, pd.DataFrame) else pd.DataFrame()
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DynamicInput",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame} if isinstance(input_frame, pd.DataFrame) else {},
        outputs=outputs,
        status="success",
        config={
            "mode": config.get("mode", ""),
            "input_configuration": config.get("input_configuration", {}),
            "modifications": config.get("modifications", {}),
            "external_input_read_performed": False,
            "input_schema": snapshot_schema(input_frame) if isinstance(input_frame, pd.DataFrame) else {},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DynamicInputTool(BaseTool):
    tool_type = "DynamicInput"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return dynamicinput_tool(inputs, config, context)
