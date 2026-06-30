import pandas as pd
import pytest

from alteryx2python.tools.test import test_tool as run_test_tool


def test_test_tool_accepts_matching_record_count(workflow_context):
    result = run_test_tool(
        {"Input": pd.DataFrame({"x": [1, 2, 3]})},
        {"tests": [{"name": "count", "connection": "#1", "type": "RecCountValue", "value": "3"}]},
        workflow_context,
    )

    assert result == {}
    assert workflow_context.traces[-1].tool_type == "Test"


def test_test_tool_matches_record_count_between_inputs(workflow_context):
    run_test_tool(
        {
            "Input": pd.DataFrame({"x": [1, 2]}),
            "Input_2": pd.DataFrame({"y": ["a", "b"]}),
        },
        {"tests": [{"name": "match", "connection": "#1", "type": "RecCountMatch", "value": "#2"}]},
        workflow_context,
    )

    assert workflow_context.traces[-1].status == "success"


def test_test_tool_evaluates_all_and_first_row_expressions(workflow_context):
    frame = pd.DataFrame({"LOCNUM": [2, 3], "flag": [False, True]})

    run_test_tool(
        {"Input": frame},
        {
            "tests": [
                {"name": "all", "connection": "#1", "type": "ExpAll", "value": "[LOCNUM] > 1"},
                {"name": "first", "connection": "#1", "type": "ExpFirst", "value": "[LOCNUM] = 2"},
            ]
        },
        workflow_context,
    )

    assert workflow_context.traces[-1].tool_type == "Test"


def test_test_tool_raises_on_failed_expression(workflow_context):
    with pytest.raises(AssertionError, match="failed"):
        run_test_tool(
            {"Input": pd.DataFrame({"LOCNUM": [1, 3]})},
            {"tests": [{"name": "all", "connection": "#1", "type": "ExpAll", "value": "[LOCNUM] > 1"}]},
            workflow_context,
        )
