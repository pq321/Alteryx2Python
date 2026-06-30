from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


__test__ = False


def _input_by_connection(inputs: dict[str, pd.DataFrame], connection: str) -> pd.DataFrame:
    normalized = connection.strip()
    if normalized.startswith("#") and normalized[1:].isdigit():
        index = int(normalized[1:])
        candidates = list(inputs.values())
        if 1 <= index <= len(candidates):
            frame = candidates[index - 1]
            if isinstance(frame, pd.DataFrame):
                return frame
    anchor = "Input" if normalized in {"", "#1"} else normalized
    if anchor not in inputs:
        raise KeyError(f"Test tool input connection is missing: {connection}")
    frame = inputs[anchor]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Test tool input anchors must contain pandas DataFrames")
    return frame


def _assert_rec_count_value(frame: pd.DataFrame, expected_text: str, name: str) -> None:
    expected = int(float(expected_text))
    actual = int(len(frame.index))
    if actual != expected:
        raise AssertionError(f"{name} failed: expected {expected} records, got {actual}")


def _assert_rec_count_match(inputs: dict[str, pd.DataFrame], frame: pd.DataFrame, expected_connection: str, name: str) -> None:
    expected_frame = _input_by_connection(inputs, expected_connection)
    actual = int(len(frame.index))
    expected = int(len(expected_frame.index))
    if actual != expected:
        raise AssertionError(f"{name} failed: expected {expected} records from {expected_connection}, got {actual}")


def _assert_expression(frame: pd.DataFrame, expression: str, mode: str, name: str) -> None:
    parsed = parse_expression(expression)
    rows = frame.head(1).to_dict("records") if mode == "ExpFirst" else frame.to_dict("records")
    for index, row in enumerate(rows):
        if not bool(evaluate_expression(parsed, row)):
            row_label = "first row" if mode == "ExpFirst" else f"row {index + 1}"
            raise AssertionError(f"{name} failed for {row_label}: {expression}")


def _run_test(inputs: dict[str, pd.DataFrame], test_config: dict[str, Any]) -> None:
    name = str(test_config.get("name", "") or "Test")
    connection = str(test_config.get("connection", "#1"))
    test_type = str(test_config.get("type", ""))
    value = str(test_config.get("value", ""))
    frame = _input_by_connection(inputs, connection)
    if test_type == "RecCountValue":
        _assert_rec_count_value(frame, value, name)
    elif test_type == "RecCountMatch":
        _assert_rec_count_match(inputs, frame, value, name)
    elif test_type in {"ExpAll", "ExpFirst"}:
        _assert_expression(frame, value, test_type, name)
    else:
        raise NotImplementedError(f"Test type is not supported: {test_type}")


def test_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    tests = [test for test in config.get("tests", []) if isinstance(test, dict)]
    if not tests:
        raise ValueError("Test tool config requires at least one test")
    for test_config in tests:
        _run_test(inputs, test_config)

    outputs: dict[str, pd.DataFrame] = {}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Test",
        source_tool_id=config.get("source_tool_id"),
        inputs={key: value for key, value in inputs.items() if isinstance(value, pd.DataFrame)},
        outputs=outputs,
        status="success",
        config={
            "tests": tests,
            "dont_report_subsequent": bool(config.get("dont_report_subsequent", False)),
        },
    )
    return outputs


class TestTool(BaseTool):
    tool_type = "Test"
    input_anchors = ("Input",)
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return test_tool(inputs, config, context)
