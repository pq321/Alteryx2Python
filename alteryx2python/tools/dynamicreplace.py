from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _frame(inputs: dict[str, pd.DataFrame], anchor: str, tool_type: str) -> pd.DataFrame:
    if anchor not in inputs:
        raise KeyError(f"{tool_type} tool requires a {anchor} anchor")
    frame = inputs[anchor]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{anchor} anchor must contain a pandas DataFrame")
    return frame


def _passes_expression(expression: str, row: dict[str, Any], context: WorkflowContext) -> bool:
    if not expression:
        return True
    try:
        return bool(evaluate_expression(parse_expression(expression), row))
    except Exception as exc:
        context.record_warning(f"DynamicReplace expression was not evaluated: {expression} ({exc})")
        return True


def _replacement_values(value: Any, is_expression: bool, output: pd.DataFrame, context: WorkflowContext) -> list[Any]:
    if not is_expression:
        return [value for _ in output.index]
    try:
        parsed = parse_expression(str(value))
        return [evaluate_expression(parsed, row) for row in output.to_dict("records")]
    except Exception as exc:
        context.record_warning(f"DynamicReplace output expression was not evaluated: {value} ({exc})")
        return [value for _ in output.index]


def dynamicreplace_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _frame(inputs, "Input", "DynamicReplace")
    expressions_frame = _frame(inputs, "Expressions", "DynamicReplace")
    field_field_name = str(config.get("field_field_name", ""))
    field_output_value = str(config.get("field_output_value", ""))
    field_expression = str(config.get("field_expression", ""))
    ensure_fields_exist(expressions_frame, [field_field_name, field_output_value])

    output = input_frame.copy()
    applied: list[dict[str, Any]] = []
    for _, expression_row in expressions_frame.iterrows():
        expression_record = expression_row.to_dict()
        output_field = str(expression_record[field_field_name])
        if not output_field or not _passes_expression(str(expression_record.get(field_expression, "")), expression_record, context):
            continue
        values = _replacement_values(
            expression_record[field_output_value],
            bool(config.get("value_is_expression", False)),
            output,
            context,
        )
        output[output_field] = values
        applied.append({"field": output_field, "value": expression_record[field_output_value]})

    counts = pd.DataFrame([{"Expressions": len(expressions_frame.index), "Applied": len(applied)}])
    outputs = {"Output": output, "Counts": counts}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DynamicReplace",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame, "Expressions": expressions_frame},
        outputs=outputs,
        status="success",
        config={
            "applied": applied,
            "value_is_expression": bool(config.get("value_is_expression", False)),
            "input_schema": snapshot_schema(input_frame),
            "expressions_schema": snapshot_schema(expressions_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DynamicReplaceTool(BaseTool):
    tool_type = "DynamicReplace"
    input_anchors = ("Input", "Expressions")
    output_anchors = ("Output", "Counts")

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return dynamicreplace_tool(inputs, config, context)
