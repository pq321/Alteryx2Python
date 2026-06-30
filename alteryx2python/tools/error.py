from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _first_row_context(inputs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for anchor, frame in inputs.items():
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        first = frame.iloc[0].to_dict()
        row.update(first)
        if len(first) == 1:
            row.setdefault(anchor, next(iter(first.values())))
    return row


def _enforce_errors(config: dict[str, Any], context: WorkflowContext) -> bool:
    runtime_config = context.runtime_config or {}
    return bool(
        config.get("enforce")
        or runtime_config.get("enforce_error_messages")
        or runtime_config.get("enforce_interface_errors")
    )


def error_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    expression = str(config.get("expression", "") or "")
    message = str(config.get("message", "") or config.get("name", "") or "Alteryx Error condition failed")
    enforced = _enforce_errors(config, context)
    matched = False

    if enforced and expression:
        parsed = parse_expression(expression)
        matched = bool(evaluate_expression(parsed, _first_row_context(inputs)))
        if matched:
            context.record_error(message)
            raise AssertionError(message)

    outputs: dict[str, pd.DataFrame] = {}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Error",
        source_tool_id=config.get("source_tool_id"),
        inputs={key: value for key, value in inputs.items() if isinstance(value, pd.DataFrame)},
        outputs=outputs,
        status="success",
        config={
            "expression": expression,
            "message": message,
            "enforce": enforced,
            "matched": matched,
        },
    )
    return outputs


class ErrorTool(BaseTool):
    tool_type = "Error"
    input_anchors = ()
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return error_tool(inputs, config, context)
