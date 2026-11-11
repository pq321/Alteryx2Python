from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.field_contracts import set_field_contract


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("Formula tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def formula_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    formula_fields = config.get("formula_fields")
    if not isinstance(formula_fields, list) or not formula_fields:
        raise ValueError("Formula tool config requires a non-empty formula_fields list")

    output = input_frame.copy()
    applied_fields: list[dict[str, Any]] = []
    for field_config in formula_fields:
        if not isinstance(field_config, dict):
            raise TypeError("Each formula_fields entry must be a dictionary")
        if field_config.get("enabled", True) is False:
            continue
        field_name = field_config.get("field")
        expression = field_config.get("expression")
        if not field_name or not expression:
            raise ValueError("Formula fields require field and expression")
        parsed_expression = parse_expression(str(expression))
        output[str(field_name)] = [
            evaluate_expression(parsed_expression, row)
            for row in output.to_dict("records")
        ]
        if field_config.get('type'):
            set_field_contract(output, str(field_name), field_config['type'], field_config.get('size'))
        applied_fields.append({"field": field_name, "expression": expression})

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Formula",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "formula_fields": applied_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class FormulaTool(BaseTool):
    tool_type = "Formula"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return formula_tool(inputs, config, context)
