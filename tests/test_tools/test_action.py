import pandas as pd

from alteryx2python.tools.action import action_tool


def test_action_tool_emits_action_payload_from_question(workflow_context):
    result = action_tool(
        {"Question": pd.DataFrame([{"tool_type": "QuestionTextBox", "value": "abc"}])},
        {"name": "Update path"},
        workflow_context,
    )

    output = result["Action"]
    assert output.loc[0, "action_name"] == "Update path"
    assert bool(output.loc[0, "active"]) is True
    assert output.loc[0, "inputs"][0]["value"] == "abc"


def test_action_tool_honors_inactive_condition_branch(workflow_context):
    result = action_tool(
        {"Condition": pd.DataFrame([{"branch": "False Condition", "active": False}])},
        {},
        workflow_context,
    )

    assert bool(result["Action"].loc[0, "active"]) is False


def test_action_tool_without_input_is_active_structural_edge(workflow_context):
    result = action_tool({}, {}, workflow_context)

    assert bool(result["Action"].loc[0, "active"]) is True
