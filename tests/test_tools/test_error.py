import pandas as pd
import pytest

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.error import error_tool


def test_error_tool_records_condition_without_enforcing(workflow_context):
    result = error_tool(
        {"Input": pd.DataFrame({"#1": [True], "#2": [""]})},
        {"expression": "[#1] AND IsEmpty([#2])", "message": "Select an input file"},
        workflow_context,
    )

    assert result == {}
    trace = workflow_context.traces[-1]
    assert trace.tool_type == "Error"
    assert trace.config["enforce"] is False
    assert trace.config["matched"] is False


def test_error_tool_raises_when_enforced_condition_matches():
    context = WorkflowContext()

    with pytest.raises(AssertionError, match="Select an input file"):
        error_tool(
            {"Input": pd.DataFrame({"#1": [True], "#2": [""]})},
            {"expression": "[#1] AND IsEmpty([#2])", "message": "Select an input file", "enforce": True},
            context,
        )

    assert context.errors == ["Select an input file"]


def test_error_tool_runtime_config_can_enable_enforcement():
    context = WorkflowContext(runtime_config={"enforce_error_messages": True})

    error_tool(
        {"Input": pd.DataFrame({"#1": [False], "#2": [""]})},
        {"expression": "[#1] AND IsEmpty([#2])", "message": "Select an input file"},
        context,
    )

    assert context.traces[-1].config["enforce"] is True
    assert context.traces[-1].config["matched"] is False
