from alteryx2python.tools.interface import (
    label_tool,
    numericupdown_tool,
    questiontab_tool,
    radiobuttongroup_tool,
)


def test_interface_value_tool_emits_question_payload(workflow_context):
    result = numericupdown_tool(
        {},
        {"name": "Limit", "prompt": "Adjust the value", "default_value": "10"},
        workflow_context,
    )

    output = result["Question"]
    assert output.to_dict("records") == [
        {"tool_type": "NumericUpDown", "name": "Limit", "prompt": "Adjust the value", "value": "10"}
    ]
    assert workflow_context.traces[-1].tool_type == "NumericUpDown"


def test_radio_button_group_uses_same_question_payload_contract(workflow_context):
    result = radiobuttongroup_tool(
        {},
        {"prompt": "Radio Button 1"},
        workflow_context,
    )

    assert result["Question"].loc[0, "tool_type"] == "RadioButtonGroup"
    assert result["Question"].loc[0, "value"] == "Radio Button 1"


def test_interface_layout_tools_are_structural_noops(workflow_context):
    label_result = label_tool({}, {"name": "Header"}, workflow_context)
    tab_result = questiontab_tool({}, {"name": "Tab"}, workflow_context)

    assert label_result == {}
    assert tab_result == {}
    assert [trace.tool_type for trace in workflow_context.traces] == ["Label", "QuestionTab"]
