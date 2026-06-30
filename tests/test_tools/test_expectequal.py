import pandas as pd
import pytest

from alteryx2python.tools.expectequal import ExpectEqualTool, expectequal_tool


def test_expectequal_records_matching_inputs(workflow_context):
    frame = pd.DataFrame({"a": [1]})

    result = expectequal_tool({"Actual": frame, "Expected": frame.copy()}, {}, workflow_context)

    assert result == {}
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "ExpectEqual"
    assert trace["config"]["matched"] is True


def test_expectequal_records_warning_for_mismatch(workflow_context):
    expectequal_tool(
        {"Actual": pd.DataFrame({"a": [1]}), "Expected": pd.DataFrame({"a": [2]})},
        {},
        workflow_context,
    )

    assert workflow_context.warnings == ["ExpectEqual comparison did not match"]
    assert workflow_context.traces[-1].to_dict()["config"]["matched"] is False


def test_expectequal_rejects_missing_anchor(workflow_context):
    with pytest.raises(KeyError, match="Expected anchor"):
        expectequal_tool({"Actual": pd.DataFrame({"a": [1]})}, {}, workflow_context)


def test_expectequal_tool_class_executes_same_contract(workflow_context):
    result = ExpectEqualTool().execute(
        {"Actual": pd.DataFrame({"a": [1]}), "Expected": pd.DataFrame({"a": [1]})},
        {},
        workflow_context,
    )

    assert result == {}
