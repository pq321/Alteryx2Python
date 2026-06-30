from __future__ import annotations

import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


MAX_GENERATED_ROWS = 100000


def _strip_comments(expression: str) -> str:
    lines = []
    for line in expression.splitlines():
        lines.append(line.split("//", 1)[0].rstrip())
    return "\n".join(line for line in lines if line.strip())


def _compile_expression(expression: str):
    return parse_expression(_strip_comments(expression))


def _seed_rows(input_frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    if input_frame is None:
        return [{}]
    return input_frame.to_dict("records")


def generaterows_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = inputs.get("Input")
    if input_frame is not None and not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    field_name = str(config.get("update_field_name") if config.get("update_field") else config.get("create_field_name"))
    if not field_name:
        raise ValueError("GenerateRows config requires a create or update field name")

    init_expr = _compile_expression(str(config.get("expression_init", "")))
    cond_expr = _compile_expression(str(config.get("expression_cond", "")))
    loop_expr = _compile_expression(str(config.get("expression_loop", "")))

    rows: list[dict[str, Any]] = []
    for seed in _seed_rows(input_frame):
        working = dict(seed)
        working[field_name] = evaluate_expression(init_expr, working)
        while bool(evaluate_expression(cond_expr, working)):
            rows.append(dict(working))
            if len(rows) > MAX_GENERATED_ROWS:
                raise RuntimeError("GenerateRows exceeded safety limit of 100000 rows")
            working[field_name] = evaluate_expression(loop_expr, working)

    output = pd.DataFrame(rows)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="GenerateRows",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame} if input_frame is not None else {},
        outputs=outputs,
        status="success",
        config={
            "field_name": field_name,
            "input_schema": snapshot_schema(input_frame) if input_frame is not None else None,
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class GenerateRowsTool(BaseTool):
    tool_type = "GenerateRows"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return generaterows_tool(inputs, config, context)
