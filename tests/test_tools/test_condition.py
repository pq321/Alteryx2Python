import pandas as pd

from alteryx2python.tools.condition import condition_tool


def test_condition_tool_emits_true_and_false_condition_payloads(workflow_context):
    result = condition_tool(
        {"Question": pd.DataFrame([{"value": "True"}])},
        {"expression": "[#1]"},
        workflow_context,
    )

    assert set(result) == {"True Condition", "False Condition"}
    assert bool(result["True Condition"].loc[0, "active"]) is True
    assert bool(result["False Condition"].loc[0, "active"]) is False
    assert workflow_context.traces[-1].tool_type == "Condition"


def test_condition_tool_supports_negated_question_expression(workflow_context):
    result = condition_tool(
        {"Question": pd.DataFrame([{"value": "True"}])},
        {"expression": "![#1]"},
        workflow_context,
    )

    assert bool(result["True Condition"].loc[0, "active"]) is False
    assert bool(result["False Condition"].loc[0, "active"]) is True


def test_condition_tool_preserves_unsupported_expression_as_warning(workflow_context):
    result = condition_tool(
        {"Question": pd.DataFrame([{"value": "abc"}])},
        {"expression": 'FindString([#1], "a")>-1'},
        workflow_context,
    )

    assert pd.isna(result["True Condition"].loc[0, "active"])
    assert workflow_context.warnings
