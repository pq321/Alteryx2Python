import pandas as pd
import pytest

from alteryx2python.tools.dynamicreplace import DynamicReplaceTool, dynamicreplace_tool


def test_dynamicreplace_assigns_scalar_values_from_expressions_input(workflow_context):
    target = pd.DataFrame({"Name": ["A", "B"]})
    expressions = pd.DataFrame({"New Field": ["Flag"], "Value": ["yes"]})

    result = dynamicreplace_tool(
        {"Input": target, "Expressions": expressions},
        {"field_field_name": "New Field", "field_output_value": "Value"},
        workflow_context,
    )

    assert result["Output"].to_dict("records") == [{"Name": "A", "Flag": "yes"}, {"Name": "B", "Flag": "yes"}]
    assert result["Counts"].to_dict("records") == [{"Expressions": 1, "Applied": 1}]


def test_dynamicreplace_evaluates_output_expression_against_target_rows(workflow_context):
    target = pd.DataFrame({"amount": [2, 3]})
    expressions = pd.DataFrame({"Name": ["double"], "Formula": ["[amount] * 2"]})

    output = dynamicreplace_tool(
        {"Input": target, "Expressions": expressions},
        {"field_field_name": "Name", "field_output_value": "Formula", "value_is_expression": True},
        workflow_context,
    )["Output"]

    assert output["double"].tolist() == [4, 6]


def test_dynamicreplace_rejects_missing_expression_columns(workflow_context):
    with pytest.raises(KeyError):
        dynamicreplace_tool(
            {"Input": pd.DataFrame({"a": [1]}), "Expressions": pd.DataFrame({"Name": ["x"]})},
            {"field_field_name": "Name", "field_output_value": "Missing"},
            workflow_context,
        )


def test_dynamicreplace_tool_class_executes_same_contract(workflow_context):
    result = DynamicReplaceTool().execute(
        {"Input": pd.DataFrame({"a": [1]}), "Expressions": pd.DataFrame({"Name": ["b"], "Value": [2]})},
        {"field_field_name": "Name", "field_output_value": "Value"},
        workflow_context,
    )

    assert result["Output"]["b"].tolist() == [2]
