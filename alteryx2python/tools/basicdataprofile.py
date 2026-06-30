from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def basicdataprofile_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("BasicDataProfile tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    rows = [
        {
            "Field": column,
            "Type": str(input_frame[column].dtype),
            "Count": int(input_frame[column].count()),
            "NullCount": int(input_frame[column].isna().sum()),
            "UniqueCount": int(input_frame[column].nunique(dropna=True)),
        }
        for column in input_frame.columns
    ]
    output = pd.DataFrame(rows)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="BasicDataProfile",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "limit_unique_count": config.get("limit_unique_count", ""),
            "limit_unique_values_size": config.get("limit_unique_values_size", ""),
            "is_metric": config.get("is_metric", False),
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class BasicDataProfileTool(BaseTool):
    tool_type = "BasicDataProfile"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return basicdataprofile_tool(inputs, config, context)
