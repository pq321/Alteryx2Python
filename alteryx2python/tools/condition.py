from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _coerce_question_value(value: Any) -> Any:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return value


def _condition_context(inputs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for index, (anchor, frame) in enumerate(inputs.items(), start=1):
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        first = frame.iloc[0].to_dict()
        value = first.get("value", next(iter(first.values()), ""))
        row[f"#{index}"] = _coerce_question_value(value)
        row[anchor] = _coerce_question_value(value)
        row.update(first)
    return row


def _evaluate_condition(expression: str, inputs: dict[str, pd.DataFrame], context: WorkflowContext) -> bool | None:
    if not expression:
        return None
    try:
        return bool(evaluate_expression(parse_expression(expression), _condition_context(inputs)))
    except Exception as exc:  # best-effort app metadata preservation
        context.record_warning(f"Condition expression was not evaluated: {expression} ({exc})")
        return None


def _condition_frame(branch: str, expression: str, matched: bool | None) -> pd.DataFrame:
    active = None if matched is None else (matched if branch == "True Condition" else not matched)
    return pd.DataFrame(
        [
            {
                "branch": branch,
                "expression": expression,
                "matched": matched,
                "active": active,
            }
        ]
    )


def condition_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    expression = str(config.get("expression", "") or "")
    matched = _evaluate_condition(expression, inputs, context)
    outputs = {
        "True Condition": _condition_frame("True Condition", expression, matched),
        "False Condition": _condition_frame("False Condition", expression, matched),
    }
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Condition",
        source_tool_id=config.get("source_tool_id"),
        inputs={key: value for key, value in inputs.items() if isinstance(value, pd.DataFrame)},
        outputs=outputs,
        status="success",
        config={
            "name": str(config.get("name", "") or ""),
            "expression": expression,
            "matched": matched,
        },
    )
    return outputs


class ConditionTool(BaseTool):
    tool_type = "Condition"
    input_anchors = ("Question",)
    output_anchors = ("True Condition", "False Condition")

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return condition_tool(inputs, config, context)
