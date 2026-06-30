import pandas as pd
import pytest

from alteryx2python.tools.filter import filter_tool


def test_filter_splits_true_and_false_outputs_preserving_order(workflow_context):
    frame = pd.DataFrame({"CustomerID": [10, 31, 45], "LastName": ["A", None, "C"]})

    result = filter_tool(
        {"Input": frame},
        {"node_id": "filter-1", "expression": "[CustomerID] > 30", "mode": "Simple"},
        workflow_context,
    )

    assert result["True"]["CustomerID"].tolist() == [31, 45]
    assert result["False"]["CustomerID"].tolist() == [10]
    assert result["True"].index.tolist() == [1, 2]
    assert result["False"].index.tolist() == [0]
    trace = workflow_context.traces[-1].to_dict()
    assert set(trace["outputs"]) == {"True", "False"}
    assert trace["outputs"]["True"]["row_count"] == 2
    assert trace["outputs"]["False"]["row_count"] == 1


def test_filter_handles_is_not_null_expression(workflow_context):
    frame = pd.DataFrame({"LastName": ["A", None, "C"]})

    result = filter_tool(
        {"Input": frame},
        {"expression": "!IsNull([LastName])", "mode": "Simple"},
        workflow_context,
    )

    assert result["True"]["LastName"].tolist() == ["A", "C"]
    assert result["False"]["LastName"].isna().tolist() == [True]


def test_filter_rejects_missing_expression(workflow_context):
    with pytest.raises(ValueError, match="requires expression"):
        filter_tool({"Input": pd.DataFrame({"x": [1]})}, {}, workflow_context)
