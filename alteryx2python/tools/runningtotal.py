from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def runningtotal_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("RunningTotal tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    group_fields = [str(field) for field in config.get("group_by_fields", [])]
    total_fields = [str(field) for field in config.get("running_total_fields", [])]
    ensure_fields_exist(input_frame, [*group_fields, *total_fields])

    output = input_frame.copy()
    for field in total_fields:
        numeric = pd.to_numeric(output[field], errors="coerce").fillna(0)
        output[f"RunningTotal_{field}"] = (
            numeric.groupby([output[group] for group in group_fields], sort=False).cumsum()
            if group_fields
            else numeric.cumsum()
        )

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="RunningTotal",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "group_by_fields": group_fields,
            "running_total_fields": total_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class RunningTotalTool(BaseTool):
    tool_type = "RunningTotal"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return runningtotal_tool(inputs, config, context)
