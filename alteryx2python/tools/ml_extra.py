"""Local, closed-form adapters for the remaining machine-learning tools.

These are deliberately small pandas/scikit-learn implementations.  They preserve
configured fields and fail closed when a Designer option has no local equivalent.
"""

from __future__ import annotations
import pickle
from typing import Any
import numpy as np
import pandas as pd
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.predictive import predictive_tool, _fields, _prepare


def _frame(inputs):
    f = inputs.get("Input")
    if f is None:
        f = inputs.get("Data")
    if f is None:
        raise KeyError("ML tool requires Input anchor")
    if not isinstance(f, pd.DataFrame):
        raise TypeError("Input anchor must be a DataFrame")
    return f


def _done(name, inputs, out, c, ctx):
    if not isinstance(ctx, WorkflowContext):
        raise TypeError("ML tool requires WorkflowContext")
    sid = c.get("source_tool_id")
    if not sid:
        raise ValueError("ML tool requires source_tool_id for execution trace")
    ctx.record_node(
        node_id=str(c.get("node_id", "unknown")),
        tool_type=name,
        source_tool_id=str(sid),
        inputs=inputs,
        outputs=out,
        status="success",
        config=dict(c),
    )
    return out


def _copy(name, inputs, c, ctx):
    return _done(name, inputs, {"Output": _frame(inputs).copy()}, c, ctx)


def feature_types(inputs, c, ctx):
    f = _frame(inputs).copy()
    types = c.get("types", c.get("configured_types", {}))
    if not isinstance(types, dict):
        raise ValueError("FeatureTypes types must be a mapping")
    for col, typ in types.items():
        if col not in f:
            raise KeyError(col)
        t = str(typ).lower()
        if t in {"numeric", "double", "float", "integer", "int"}:
            f[col] = pd.to_numeric(f[col], errors="raise")
        elif t in {"string", "v_string", "categorical"}:
            f[col] = f[col].astype("string")
        else:
            raise ValueError(f"unsupported FeatureTypes type: {typ}")
    return _done("FeatureTypes", inputs, {"Output": f}, c, ctx)


def data_health(inputs, c, ctx):
    f = _frame(inputs)
    out = pd.DataFrame(
        {
            "Field": list(f.columns),
            "Records": [len(f)] * len(f.columns),
            "NullCount": [int(f[x].isna().sum()) for x in f],
            "UniqueCount": [int(f[x].nunique(dropna=True)) for x in f],
        }
    )
    return _done("DataHealth", inputs, {"Output": out}, c, ctx)


def build_features(inputs, c, ctx):
    f = _frame(inputs).copy()
    expressions = c.get("expressions", {})
    if not expressions or not isinstance(expressions, dict):
        raise ValueError("BuildFeatures requires configured expressions")
    for name, expr in expressions.items():
        if not isinstance(expr, str):
            raise ValueError("BuildFeatures expressions must be strings")
        f[name] = f.eval(expr, engine="python")
    return _done("BuildFeatures", inputs, {"Output": f}, c, ctx)


def transform(inputs, c, ctx):
    f = _frame(inputs).copy()
    fields = c.get("fields") or list(f.select_dtypes(include=np.number).columns)
    mode = str(c.get("method", "standardize")).lower()
    if mode not in {"standardize", "normalize", "log1p"}:
        raise ValueError(f"unsupported Transformation method: {mode}")
    for col in fields:
        if col not in f:
            raise KeyError(col)
        x = pd.to_numeric(f[col], errors="raise")
        if mode == "standardize":
            f[col] = (x - x.mean()) / (x.std(ddof=0) or 1)
        elif mode == "normalize":
            f[col] = x / (np.sqrt((x * x).sum()) or 1)
        else:
            if (x < 0).any():
                raise ValueError("log1p requires non-negative values")
            f[col] = np.log1p(x)
    return _done("Transformation", inputs, {"Output": f}, c, ctx)


def _pred(kind):
    return lambda inputs, c, ctx: predictive_tool(kind, inputs, c, ctx)


def _model(kind):
    def run(inputs, c, ctx):
        from sklearn.pipeline import Pipeline
        from sklearn.linear_model import Ridge, LogisticRegression
        from sklearn.ensemble import (
            GradientBoostingRegressor,
            GradientBoostingClassifier,
        )
        from sklearn.neural_network import MLPRegressor, MLPClassifier
        from sklearn.svm import SVR, SVC
        from sklearn.preprocessing import SplineTransformer
        from sklearn.feature_selection import SequentialFeatureSelector

        f = _frame(inputs)
        cols, target = _fields(f, c)
        classification = bool(
            c.get(
                "classification", f[target].dtype == object or f[target].nunique() <= 2
            )
        )
        opts = dict(c.get("options", {}))
        seed = c.get("random_state", 0)
        if kind == "BoostedModel":
            est = (
                GradientBoostingClassifier
                if classification
                else GradientBoostingRegressor
            )(random_state=seed, **opts)
        elif kind == "NeuralNetwork":
            est = (MLPClassifier if classification else MLPRegressor)(
                random_state=seed, max_iter=1000, **opts
            )
        elif kind == "SupportVectorMachine":
            est = (SVC if classification else SVR)(**opts)
        elif kind == "SplineModel":
            est = Pipeline(
                [
                    (
                        "spline",
                        SplineTransformer(
                            n_knots=int(c.get("knots", 5)),
                            degree=int(c.get("degree", 3)),
                        ),
                    ),
                    ("model", Ridge(**opts)),
                ]
            )
        elif kind == "Stepwise":
            base = LogisticRegression(max_iter=1000) if classification else Ridge()
            est = (
                base
                if len(cols) < 2
                else SequentialFeatureSelector(
                    base,
                    n_features_to_select=c.get("n_features_to_select", "auto"),
                    direction=c.get("direction", "forward"),
                )
            )
        else:
            raise NotImplementedError(kind)
        pre = _prepare(f, cols)
        pipe = Pipeline([("prepare", pre), ("model", est)])
        pipe.fit(f[cols], f[target])
        pred = pipe.predict(f[cols])
        out = f.copy()
        out[c.get("prediction_field", "Prediction")] = pred
        result = _done(kind, inputs, {"Output": out}, c, ctx)
        ctx.traces[-1].config["algorithm"] = kind
        return result

    return run


def cross_validation(inputs, c, ctx):
    from sklearn.model_selection import cross_val_score
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import Pipeline

    f = _frame(inputs)
    cols, target = _fields(f, c)
    est = LinearRegression()
    pipe = Pipeline([("prepare", _prepare(f, cols)), ("model", est)])
    y = f[target]
    folds = int(c.get("folds", 5))
    scores = cross_val_score(pipe, f[cols], y, cv=folds, scoring=c.get("scoring", "r2"))
    return _done(
        "CrossValidation",
        inputs,
        {"Output": pd.DataFrame({"Fold": range(1, len(scores) + 1), "Score": scores})},
        c,
        ctx,
    )


def nested_test(inputs, c, ctx):
    import statsmodels.api as sm

    f = _frame(inputs)
    target = c.get("target")
    full = list(c.get("full_fields", []))
    reduced = list(c.get("reduced_fields", []))
    if not target or not full or not reduced or not set(reduced) < set(full):
        raise ValueError(
            "NestedTest requires target, strict full_fields and reduced_fields"
        )
    y = pd.to_numeric(f[target], errors="raise")
    reduced_fit = sm.OLS(y, sm.add_constant(f[reduced])).fit()
    full_fit = sm.OLS(y, sm.add_constant(f[full])).fit()
    stat, pval, dfdiff = full_fit.compare_f_test(reduced_fit)
    return _done(
        "NestedTest",
        inputs,
        {
            "Output": pd.DataFrame(
                {"FStatistic": [stat], "PValue": [pval], "DFDifference": [dfdiff]}
            )
        },
        c,
        ctx,
    )


def mbaffinity(inputs, c, ctx, tool_name="MBAffinity"):
    f = _frame(inputs)
    fields = c.get("fields") or list(f.columns)
    min_support = float(c.get("min_support", 0.1))
    rows = []
    if not c.get("transaction_id"):
        raise ValueError("MBA tools require transaction_id")
    tid = c["transaction_id"]
    items = c.get("item_fields", fields)
    present = f[items].apply(lambda s: s.astype(bool) & s.notna())
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            a, b = items[a], items[b]
            pa = present[a].groupby(f[tid]).max()
            pb = present[b].groupby(f[tid]).max()
            support = float((pa & pb).mean())
            sa = float(pa.mean())
            sb = float(pb.mean())
            if support >= min_support:
                rows.append(
                    {
                        "ItemA": a,
                        "ItemB": b,
                        "Support": support,
                        "ConfidenceAtoB": support / sa if sa else np.nan,
                        "Lift": support / (sa * sb) if sa * sb else np.nan,
                    }
                )
    return _done(
        tool_name,
        inputs,
        {
            "Output": pd.DataFrame(
                rows, columns=["ItemA", "ItemB", "Support", "ConfidenceAtoB", "Lift"]
            )
        },
        c,
        ctx,
    )


def automl(inputs, c, ctx):
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import Pipeline
    from alteryx2python.tools.predictive import _estimator

    frame = _frame(inputs)
    fields, target = _fields(frame, c)
    candidates = c.get("candidates", ["LinearRegression", "ForestModel"])
    if not candidates:
        raise ValueError("AutoML candidates cannot be empty")
    scores = []
    for candidate in candidates:
        if candidate not in {"LinearRegression", "ForestModel", "LogisticRegression"}:
            raise NotImplementedError(f"unsupported AutoML candidate: {candidate}")
        estimator = _estimator(candidate, c)
        pipeline = Pipeline(
            [("prepare", _prepare(frame, fields)), ("model", estimator)]
        )
        scoring = c.get(
            "scoring",
            "accuracy"
            if candidate == "LogisticRegression"
            else "neg_mean_squared_error",
        )
        score = cross_val_score(
            pipeline,
            frame[fields],
            frame[target],
            cv=int(c.get("folds", 3)),
            scoring=scoring,
            error_score="raise",
        ).mean()
        scores.append((candidate, float(score)))
    best = max(scores, key=lambda x: x[1])[0]
    r = predictive_tool(best, inputs, c, ctx)
    ctx.traces[-1].tool_type = "AutoML"
    ctx.traces[-1].config["selected_algorithm"] = best
    return r


def stepwise(inputs, c, ctx):
    import statsmodels.api as sm

    f = _frame(inputs)
    target = c.get("target")
    fields = list(c.get("predictors") or [])
    criterion = str(c.get("criterion", "AIC")).upper()
    if not target or not fields or criterion not in {"AIC", "BIC"}:
        raise ValueError("Stepwise requires target, predictors, and AIC/BIC")
    y = pd.to_numeric(f[target], errors="raise")
    selected = fields[:]

    def fit(cols):
        return sm.OLS(y, sm.add_constant(f[cols])).fit()

    current = fit(selected)
    while len(selected) > 1:
        choices = [
            (getattr(fit([x for x in selected if x != col]), criterion.lower()), col)
            for col in selected
        ]
        score, col = min(choices)
        if score < getattr(current, criterion.lower()):
            selected.remove(col)
            current = fit(selected)
        else:
            break
    out = f.copy()
    out["Prediction"] = current.predict(sm.add_constant(f[selected]))
    return _done(
        "Stepwise",
        inputs,
        {"Output": out, "Model": pd.DataFrame({"SelectedField": selected})},
        c,
        ctx,
    )


IMPLEMENTATIONS = {
    "FeatureTypes": feature_types,
    "DataHealth": data_health,
    "BuildFeatures": build_features,
    "Transformation": transform,
    "AutoML": automl,
    "Modeling": _model("BoostedModel"),
    "Insights": data_health,
    "BoostedModel": _model("BoostedModel"),
    "NeuralNetwork": _model("NeuralNetwork"),
    "SupportVectorMachine": _model("SupportVectorMachine"),
    "SplineModel": _model("SplineModel"),
    "Stepwise": stepwise,
    "CrossValidation": cross_validation,
    "NestedTest": nested_test,
    "MBAffinity": mbaffinity,
    "MBInspect": lambda i, c, x: mbaffinity(i, c, x, "MBInspect"),
    "MBRules": lambda i, c, x: mbaffinity(i, c, x, "MBRules"),
}
ANCHORS = {k: (("Input",), ("Output",)) for k in IMPLEMENTATIONS}
ANCHORS["AutoML"] = (("Input",), ("Output", "Predictions", "O", "R"))
ANCHORS["Stepwise"] = (("Input",), ("Output", "Model"))
try:
    from alteryx2python.parser.tool_parsers.ml_tool_parser import make_ml_parser

    PARSERS = {k: make_ml_parser(k) for k in IMPLEMENTATIONS}
except ImportError:
    PARSERS = {}
