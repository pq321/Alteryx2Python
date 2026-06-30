from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _size(series: pd.Series) -> int:
    if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
        return int(series.dropna().astype(str).map(len).max() or 0)
    return 0


def fieldinfo_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("FieldInfo tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    output = pd.DataFrame(
        [
            {
                "Name": column,
                "Type": str(input_frame[column].dtype),
                "Size": _size(input_frame[column]),
                "Scale": 0,
                "Source": "",
                "Description": "",
            }
            for column in input_frame.columns
        ]
    )
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="FieldInfo",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={"input_schema": snapshot_schema(input_frame), "output_schema": snapshot_schema(output)},
    )
    return outputs


class FieldInfoTool(BaseTool):
    tool_type = "FieldInfo"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return fieldinfo_tool(inputs, config, context)
