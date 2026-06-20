from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def dynamicrename_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Targets" not in inputs:
        raise KeyError("DynamicRename tool requires a Targets anchor")
    input_frame = inputs["Targets"]
    rename_mode = str(config.get("rename_mode", ""))
    expression = str(config.get("expression", ""))
    if rename_mode.lower() != "formula" or not expression:
        raise NotImplementedError("DynamicRename currently supports only Formula mode")

    parsed_expression = parse_expression(expression)
    rename_map = {
        column: evaluate_expression(parsed_expression, {"_CurrentField_": column})
        for column in input_frame.columns
    }
    if len(set(rename_map.values())) != len(rename_map):
        raise ValueError("DynamicRename produced duplicate output field names")

    output = input_frame.rename(columns=rename_map)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DynamicRename",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Targets": input_frame},
        outputs=outputs,
        status="success",
        config={
            "rename_mode": rename_mode,
            "expression": expression,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DynamicRenameTool(BaseTool):
    tool_type = "DynamicRename"
    input_anchors = ("Targets",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return dynamicrename_tool(inputs, config, context)
