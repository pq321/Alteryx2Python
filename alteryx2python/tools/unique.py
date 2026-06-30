from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def unique_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Unique tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    unique_fields = [str(field) for field in config.get("unique_fields", [])]
    if not unique_fields:
        unique_fields = list(input_frame.columns)
    ensure_fields_exist(input_frame, unique_fields)

    duplicate_mask = input_frame.duplicated(subset=unique_fields, keep="first")
    unique_output = input_frame.loc[~duplicate_mask].copy()
    duplicate_output = input_frame.loc[duplicate_mask].copy()
    outputs = {"Unique": unique_output, "Duplicate": duplicate_output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Unique",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "unique_fields": unique_fields,
            "input_schema": snapshot_schema(input_frame),
            "unique_schema": snapshot_schema(unique_output),
            "duplicate_schema": snapshot_schema(duplicate_output),
        },
    )
    return outputs


class UniqueTool(BaseTool):
    tool_type = "Unique"
    input_anchors = ("Input",)
    output_anchors = ("Unique", "Duplicate")

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return unique_tool(inputs, config, context)
