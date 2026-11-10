import pandas as pd
import pytest
from alteryx2python.tools.survival import survival_tool


def test_test_of_means(workflow_context):
    out = survival_tool(
        "TestofMeans",
        {"Input": pd.DataFrame({"A": [1, 2, 3, 4], "B": [1, 1, 1, 1]})},
        {"source_tool_id": "t"},
        workflow_context,
    )["R"]
    assert out.loc[0, "Statistic"] > 0


def test_survival_fit_score_new_rows(workflow_context):
    train = pd.DataFrame(
        {
            "time": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "event": [1, 1, 1, 0, 1, 0],
            "x": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    model = survival_tool(
        "SurvivalAnalysis",
        {"Input": train},
        {
            "duration_field": "time",
            "event_field": "event",
            "predictors": ["x"],
            "source_tool_id": "s",
        },
        workflow_context,
    )["O"]
    out = survival_tool(
        "SurvivalScore",
        {"Input": pd.DataFrame({"x": [6.0, 7.0]}), "Model": model},
        {"source_tool_id": "q"},
        workflow_context,
    )["O"]
    assert "RiskScore" in out and len(out) == 2


def test_survival_score_requires_model(workflow_context):
    with pytest.raises(ValueError):
        survival_tool(
            "SurvivalScore",
            {"Input": pd.DataFrame({"x": [1.0]})},
            {"source_tool_id": "q"},
            workflow_context,
        )


def test_paired_means_preserves_pairs_when_nulls_differ(workflow_context):
    from scipy.stats import ttest_rel

    frame = pd.DataFrame(
        {"A": [1.0, None, 7.0, 9.0, 12.0], "B": [None, 3.0, 6.0, 5.0, 9.0]}
    )
    actual = survival_tool(
        "TestofMeans",
        {"Input": frame},
        {"source_tool_id": "t", "mode": "paired"},
        workflow_context,
    )["R"]
    expected = ttest_rel([7.0, 9.0, 12.0], [6.0, 5.0, 9.0])
    assert actual.loc[0, "Statistic"] == pytest.approx(expected.statistic)
