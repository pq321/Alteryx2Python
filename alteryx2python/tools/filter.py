from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def filter_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Filter tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    expression = config.get("expression")
    if config.get('unsupported_operator'):
        raise NotImplementedError(f"Simple Filter operator requires a template: {config['unsupported_operator']}")
    if not expression:
        raise ValueError("Filter tool config requires expression")

    parsed_expression = parse_expression(str(expression))
    mask = pd.Series(
        [bool(evaluate_expression(parsed_expression, row)) for row in input_frame.to_dict("records")],
        index=input_frame.index,
    )
    true_frame = input_frame.loc[mask].copy()
    false_frame = input_frame.loc[~mask].copy()
    outputs = {"True": true_frame, "False": false_frame}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Filter",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "expression": expression,
            "mode": config.get("mode"),
            "input_schema": snapshot_schema(input_frame),
            "true_schema": snapshot_schema(true_frame),
            "false_schema": snapshot_schema(false_frame),
        },
    )
    return outputs


class FilterTool(BaseTool):
    tool_type = "Filter"
    input_anchors = ("Input",)
    output_anchors = ("True", "False")

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return filter_tool(inputs, config, context)
