from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def apioutput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = inputs.get("Input")
    if input_frame is not None and not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="APIOutput",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame} if isinstance(input_frame, pd.DataFrame) else {},
        outputs={},
        status="success",
        config={
            "external_api_write_performed": False,
            "input_schema": snapshot_schema(input_frame) if isinstance(input_frame, pd.DataFrame) else {},
        },
    )
    return {}


class APIOutputTool(BaseTool):
    tool_type = "APIOutput"
    input_anchors = ("Input",)
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return apioutput_tool(inputs, config, context)
