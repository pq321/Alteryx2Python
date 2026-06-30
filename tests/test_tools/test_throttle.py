import pandas as pd
import pytest

from alteryx2python.tools.throttle import ThrottleTool, throttle_tool


def test_throttle_passes_input_to_output(workflow_context):
    frame = pd.DataFrame({"a": [1, 2]})

    result = throttle_tool({"Input": frame}, {"records_per_minute": "60"}, workflow_context)

    assert result["Output"].to_dict("records") == [{"a": 1}, {"a": 2}]
    assert result["Output"] is not frame
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "Throttle"
    assert trace["config"]["records_per_minute"] == "60"


def test_throttle_rejects_missing_input(workflow_context):
    with pytest.raises(KeyError, match="requires an Input anchor"):
        throttle_tool({}, {}, workflow_context)


def test_throttle_tool_class_executes_same_contract(workflow_context):
    result = ThrottleTool().execute({"Input": pd.DataFrame({"a": [1]})}, {}, workflow_context)

    assert result["Output"]["a"].tolist() == [1]
