import pandas as pd
import pytest

from alteryx2python.tools.pearsoncorrelation import pearsoncorrelation_tool


def test_pearsoncorrelation_outputs_pairwise_correlations_and_covariance(workflow_context):
    frame = pd.DataFrame(
        {
            "x": [1, 2, 3],
            "y": [2, 4, 6],
            "z": [3, 2, 1],
        }
    )

    result = pearsoncorrelation_tool(
        {"Input": frame},
        {"fields": ["x", "y", "z"], "covariance": True},
        workflow_context,
    )

    assert result["Output"].to_dict("records") == [
        {"Field1": "x", "Field2": "y", "Correlation": pytest.approx(1.0), "Covariance": pytest.approx(2.0)},
        {"Field1": "x", "Field2": "z", "Correlation": pytest.approx(-1.0), "Covariance": pytest.approx(-1.0)},
        {"Field1": "y", "Field2": "z", "Correlation": pytest.approx(-1.0), "Covariance": pytest.approx(-2.0)},
    ]
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "PearsonCorrelation"


def test_pearsoncorrelation_expands_unknown_to_remaining_numeric_fields(workflow_context):
    frame = pd.DataFrame(
        {
            "x": [1, 2, 3],
            "label": ["a", "b", "c"],
            "y": [1, 4, 9],
        }
    )

    result = pearsoncorrelation_tool(
        {"Input": frame},
        {"fields": ["x", "*Unknown"], "covariance": False},
        workflow_context,
    )

    assert list(result["Output"]["Field2"]) == ["y"]


def test_pearsoncorrelation_rejects_non_numeric_selected_fields(workflow_context):
    with pytest.raises(ValueError, match="numeric and non-null"):
        pearsoncorrelation_tool(
            {"Input": pd.DataFrame({"x": [1, 2], "label": ["a", "b"]})},
            {"fields": ["x", "label"], "covariance": False},
            workflow_context,
        )
