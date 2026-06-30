from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _selected_fields(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    configured = [str(field) for field in config.get("fields", [])]
    explicit = [field for field in configured if field != "*Unknown" and field in frame.columns]
    if "*Unknown" in configured:
        explicit.extend(column for column in frame.columns if column not in explicit)
    return explicit or list(frame.columns)


def _output_field_name(field: str, config: dict[str, Any]) -> str:
    if not config.get("copy_output"):
        return field
    addon = str(config.get("new_field_add_on", ""))
    if str(config.get("new_field_add_on_pos", "Suffix")).lower() == "prefix":
        return f"{addon}{field}"
    return f"{field}{addon}"


def multifieldformula_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("MultiFieldFormula tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    expression = str(config.get("expression", ""))
    if not expression:
        raise ValueError("MultiFieldFormula config requires expression")

    parsed = parse_expression(expression)
    output = input_frame.copy()
    applied: list[dict[str, str]] = []
    for field in _selected_fields(input_frame, config):
        output_field = _output_field_name(field, config)
        values = []
        for row in output.to_dict("records"):
            scoped_row = {**row, "_CurrentField_": row[field]}
            values.append(evaluate_expression(parsed, scoped_row))
        output[output_field] = values
        applied.append({"field": field, "output_field": output_field})

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="MultiFieldFormula",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "expression": expression,
            "applied_fields": applied,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class MultiFieldFormulaTool(BaseTool):
    tool_type = "MultiFieldFormula"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return multifieldformula_tool(inputs, config, context)
