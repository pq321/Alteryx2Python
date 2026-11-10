"""Local predictive/statistical tool implementations.

These adapters intentionally use an internal Python model representation; they do
not claim byte-for-byte compatibility with Alteryx/R model blobs.
"""

from __future__ import annotations

from typing import Any, Callable
import pickle
import json

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext


def _input(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = inputs.get("Input")
    if frame is None:
        frame = inputs.get("Data")
    if frame is None:
        raise KeyError("predictive tool requires an Input anchor")
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _fields(
    frame: pd.DataFrame, config: dict[str, Any], *, target_required: bool = True
) -> tuple[list[str], str | None]:
    target = (
        config.get("target")
        or config.get("target_field")
        or config.get("response")
        or config.get("target_variable")
        or config.get("TargetVariable")
    )
    targets = config.get("targets")
    if targets and not target:
        target = targets[0] if isinstance(targets, (list, tuple)) else targets
    predictors = (
        config.get("predictors")
        or config.get("features")
        or config.get("feature_fields")
    )
    if isinstance(predictors, str):
        predictors = [x.strip() for x in predictors.split(",") if x.strip()]
    if not predictors:
        predictors = [c for c in frame.columns if c != target]
    if not target and target_required:
        raise ValueError("predictive tool requires configured target/response field")
    missing = [
        c
        for c in ([str(target)] if target else []) + list(map(str, predictors))
        if c not in frame.columns
    ]
    if missing:
        raise KeyError(f"configured predictive fields are missing: {missing}")
    return list(map(str, predictors)), str(target) if target else None


def _sklearn():
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler

        return ColumnTransformer, SimpleImputer, Pipeline, OneHotEncoder, StandardScaler
    except ImportError as exc:
        raise RuntimeError(
            "predictive tools require optional dependency scikit-learn"
        ) from exc


def _estimator(kind: str, config: dict[str, Any]):
    if kind == "Fit":
        kind = str(config.get("algorithm", "LinearRegression"))
    kind = {
        "Regression": "LinearRegression",
        "Classification": "LogisticRegression",
    }.get(kind, kind)
    selection = config.get("algorithm_selection")
    if selection:
        choices = {
            "linear_regression": "LinearRegression",
            "logistic_regression": "LogisticRegression",
            "decision_tree": "DecisionTree",
            "decision_tree_regressor": "DecisionTree",
            "random_forest": "ForestModel",
            "random_forest_regressor": "ForestModel",
            "naive_bayes": "NaiveBayes",
        }
        if selection not in choices:
            raise NotImplementedError(f"Unsupported configured algorithm: {selection}")
        kind = choices[selection]
        config = {
            **config,
            "classification": not str(selection).endswith("_regressor")
            and selection != "linear_regression",
        }
    try:
        from sklearn.linear_model import LinearRegression, LogisticRegression
        from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.naive_bayes import GaussianNB
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA
    except ImportError as exc:
        raise RuntimeError(
            "predictive tools require optional dependency scikit-learn"
        ) from exc
    opts = {k: v for k, v in config.get("options", {}).items() if v is not None}
    seed = config.get("random_state", config.get("seed", 0))
    if kind == "LinearRegression":
        return LinearRegression(**opts)
    if kind == "LogisticRegression":
        return LogisticRegression(random_state=seed, **opts)
    if kind == "DecisionTree":
        cls = (
            DecisionTreeClassifier
            if config.get("classification", False)
            else DecisionTreeRegressor
        )
        return cls(random_state=seed, **opts)
    if kind == "ForestModel":
        cls = (
            RandomForestClassifier
            if config.get("classification", False)
            else RandomForestRegressor
        )
        return cls(random_state=seed, **opts)
    if kind == "NaiveBayes":
        return GaussianNB(**opts)
    if kind == "KCentroidsClusterAnalysis":
        return KMeans(random_state=seed, n_init=opts.pop("n_init", 10), **opts)
    if kind == "PrincipalComponents":
        return PCA(**opts)
    raise NotImplementedError(f"unsupported predictive algorithm: {kind}")


def _prepare(frame: pd.DataFrame, columns: list[str]):
    ColumnTransformer, SimpleImputer, Pipeline, OneHotEncoder, StandardScaler = (
        _sklearn()
    )
    numeric = [c for c in columns if pd.api.types.is_numeric_dtype(frame[c])]
    categorical = [c for c in columns if c not in numeric]
    transformers = []
    if numeric:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            )
        )
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            )
        )
    return ColumnTransformer(transformers, remainder="drop")


def predictive_tool(
    kind: str,
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if not isinstance(context, WorkflowContext):
        raise TypeError("predictive tool requires a WorkflowContext")
    if not config.get("source_tool_id"):
        raise ValueError("predictive tool requires source_tool_id for execution trace")
    frame = pd.DataFrame() if kind == "ModelCoefficients" else _input(inputs)
    inference = kind in ("Predict", "Score", "ModelCoefficients")
    if inference:
        model_frame = inputs.get("Model")
        if model_frame is None:
            model_frame = inputs.get("O")
        if (
            model_frame is None
            or "model_blob" not in model_frame.columns
            or model_frame.empty
        ):
            raise ValueError(
                f"{kind} requires a fitted Model/O anchor containing model_blob"
            )
        try:
            pipe = pickle.loads(model_frame.iloc[0]["model_blob"])
        except Exception as exc:
            raise ValueError("invalid predictive model artifact") from exc
        if kind == "ModelCoefficients":
            estimator = pipe.named_steps.get("model", pipe)
            coef = getattr(estimator, "coef_", None)
            if coef is None:
                raise ValueError("fitted model does not expose coefficients")
            values = list(coef[0] if getattr(coef, "ndim", 1) > 1 else coef)
            outputs = {"R": pd.DataFrame({"Coefficient": values})}
            context.record_node(
                node_id=str(config.get("node_id", "unknown")),
                tool_type=kind,
                source_tool_id=str(config["source_tool_id"]),
                inputs=inputs,
                outputs=outputs,
                status="success",
                config={
                    "model_representation": "pickle bytes of local sklearn pipeline"
                },
            )
            return outputs
        pred = pipe.predict(frame)
        name = config.get("prediction_field", "Prediction")
        out = frame.copy()
        out[name] = pred
        outputs = {"O": out}
        context.record_node(
            node_id=str(config.get("node_id", "unknown")),
            tool_type=kind,
            source_tool_id=str(config["source_tool_id"]),
            inputs=inputs,
            outputs=outputs,
            status="success",
            config={
                "model_representation": "pickle bytes of local sklearn pipeline",
                "prediction_field": name,
            },
        )
        return outputs
    predictors, target = _fields(
        frame,
        config,
        target_required=kind
        not in ("PrincipalComponents", "KCentroidsClusterAnalysis"),
    )
    model = _estimator(kind, config)
    x = frame[predictors]
    y = frame[target] if target else None
    if kind == "PrincipalComponents":
        transformed = model.fit_transform(_prepare(frame, predictors).fit_transform(x))
        out = pd.DataFrame(
            transformed,
            index=frame.index,
            columns=[f"PC{i + 1}" for i in range(transformed.shape[1])],
        )
        outputs = {"Output": out}
    elif kind == "KCentroidsClusterAnalysis":
        transformed = _prepare(frame, predictors).fit_transform(x)
        labels = model.fit_predict(transformed)
        out = frame.copy()
        out[config.get("cluster_field", "Cluster")] = labels
        outputs = {"Output": out}
    else:
        if target is None:
            raise ValueError(f"{kind} requires a target field")
        pre = _prepare(frame, predictors)
        pipe = __import__("sklearn.pipeline", fromlist=["Pipeline"]).Pipeline(
            [("prepare", pre), ("model", model)]
        )
        pipe.fit(x, y)
        if kind == "Fit":
            blob = pickle.dumps(pipe, protocol=pickle.HIGHEST_PROTOCOL)
            outputs = {
                "O": pd.DataFrame(
                    {
                        "model_blob": [blob],
                        "model_type": [config.get("algorithm", "LinearRegression")],
                        "target_field": [target],
                        "feature_fields": [json.dumps(predictors)],
                    }
                )
            }
            context.record_node(
                node_id=str(config.get("node_id", "unknown")),
                tool_type=kind,
                source_tool_id=str(config["source_tool_id"]),
                inputs={"Input": frame},
                outputs=outputs,
                status="success",
                config={
                    "model_representation": "pickle bytes of local sklearn pipeline"
                },
            )
            return outputs
        pred = pipe.predict(x)
        out = frame.copy()
        out[config.get("prediction_field", "Prediction")] = pred
        outputs = {
            "Output": out,
            "Predictions": out[
                [target, config.get("prediction_field", "Prediction")]
            ].copy(),
            "O": pd.DataFrame(
                {
                    "model_blob": [
                        pickle.dumps(pipe, protocol=pickle.HIGHEST_PROTOCOL)
                    ],
                    "target_field": [target],
                    "feature_fields": [json.dumps(predictors)],
                }
            ),
            "R": pd.DataFrame(
                {"Target": [target], "TrainingRows": [len(frame)], "Algorithm": [kind]}
            ),
        }
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=kind,
        source_tool_id=str(config["source_tool_id"]),
        inputs={"Input": frame},
        outputs=outputs,
        status="success",
        config={
            "predictors": predictors,
            "target": target,
            "input_schema": snapshot_schema(frame),
            "output_schema": {k: snapshot_schema(v) for k, v in outputs.items()},
            "model_representation": "internal sklearn artifact",
            "algorithm": kind,
        },
    )
    return outputs


def make_tool(kind: str) -> Callable[..., dict[str, pd.DataFrame]]:
    return lambda inputs, config, context: predictive_tool(
        kind, inputs, config, context
    )


_KINDS = (
    "LinearRegression",
    "LogisticRegression",
    "DecisionTree",
    "ForestModel",
    "NaiveBayes",
    "KCentroidsClusterAnalysis",
    "PrincipalComponents",
)
IMPLEMENTATIONS = {kind: make_tool(kind) for kind in _KINDS}
for alias, kind in {
    "ModelCoefficients": "LinearRegression",
    "Score": "LogisticRegression",
    "Fit": "LinearRegression",
    "Predict": "LinearRegression",
    "Regression": "LinearRegression",
    "Classification": "LogisticRegression",
}.items():
    IMPLEMENTATIONS[alias] = make_tool(alias)
IMPLEMENTATIONS["NaiveBayesClassifier"] = make_tool("NaiveBayes")

ANCHORS = {
    kind: (("Input",), ("Output", "Predictions", "O", "R")) for kind in IMPLEMENTATIONS
}
for _name in ("PrincipalComponents", "KCentroidsClusterAnalysis"):
    ANCHORS[_name] = (("Input",), ("Output",))
ANCHORS.update(
    {
        "Fit": (("Input",), ("O",)),
        "Predict": (("Input", "Model"), ("O",)),
        "Score": (("Input", "Model"), ("O",)),
        "ModelCoefficients": (("Model",), ("R",)),
    }
)
# Existing ML parser normalizes native XML into algorithm_selection,
# algorithm_configs, target_variable, schema_id, etc.; expose those parsers
# without changing the shared parser registry.
try:
    from alteryx2python.parser.tool_parsers.ml_tool_parser import make_ml_parser

    PARSERS = {
        name: make_ml_parser(name)
        for name in (
            "Classification",
            "Regression",
            "Transformation",
            "Fit",
            "Predict",
            "FeatureTypes",
        )
    }
except ImportError:  # pragma: no cover - base installs may omit parser extras
    PARSERS = {}
