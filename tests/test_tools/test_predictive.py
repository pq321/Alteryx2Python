import pandas as pd
import pytest

from alteryx2python.tools.predictive import predictive_tool


def test_linear_regression_real_fit(workflow_context):
    frame = pd.DataFrame({"x": [0, 1, 2, 3], "y": [1.0, 3.0, 5.0, 7.0]})
    out = predictive_tool("LinearRegression", {"Input": frame}, {"target": "y", "predictors": ["x"], "source_tool_id": "1"}, workflow_context)["Output"]
    assert out["Prediction"].round(6).tolist() == frame["y"].tolist()
    assert workflow_context.traces[-1].status == "success"


def test_logistic_regression_and_categorical_input(workflow_context):
    frame = pd.DataFrame({"kind": ["a", "a", "b", "b"], "y": [0, 0, 1, 1]})
    out = predictive_tool("LogisticRegression", {"Input": frame}, {"target": "y", "predictors": ["kind"], "source_tool_id": "2"}, workflow_context)["Output"]
    assert out["Prediction"].tolist() == frame["y"].tolist()


def test_missing_configured_field_fails(workflow_context):
    with pytest.raises(KeyError):
        predictive_tool("LinearRegression", {"Input": pd.DataFrame({"x": [1]}),}, {"target": "missing", "source_tool_id": "3"}, workflow_context)


def test_unsupported_algorithm_fails_closed(workflow_context):
    with pytest.raises(NotImplementedError):
        predictive_tool("NotAnAlgorithm", {"Input": pd.DataFrame({"x": [1], "y": [2]})}, {"target": "y", "source_tool_id": "4"}, workflow_context)


def test_pca_and_clusters_are_unsupervised(workflow_context):
    frame = pd.DataFrame({"x": [0., 1., 10., 11.], "z": [0., 1., 10., 11.]})
    pca = predictive_tool("PrincipalComponents", {"Input": frame}, {"predictors": ["x", "z"], "source_tool_id": "5"}, workflow_context)["Output"]
    clusters = predictive_tool("KCentroidsClusterAnalysis", {"Input": frame}, {"predictors": ["x", "z"], "options": {"n_clusters": 2}, "source_tool_id": "6"}, workflow_context)["Output"]
    assert pca.shape == (4, 2)
    assert clusters["Cluster"].nunique() == 2


def test_fit_then_predict_new_data_without_target(workflow_context):
    train = pd.DataFrame({"x": [0., 1., 2., 3.], "y": [1., 3., 5., 7.]})
    fitted = predictive_tool("Fit", {"Input": train}, {"target": "y", "predictors": ["x"], "source_tool_id": "7"}, workflow_context)["O"]
    new = pd.DataFrame({"x": [4., 5.]})
    out = predictive_tool("Predict", {"Input": new, "Model": fitted}, {"source_tool_id": "8"}, workflow_context)["O"]
    assert out["Prediction"].round(6).tolist() == [9.0, 11.0]


def test_predict_rejects_missing_model(workflow_context):
    with pytest.raises(ValueError):
        predictive_tool("Predict", {"Input": pd.DataFrame({"x": [1.]})}, {"source_tool_id": "9"}, workflow_context)
