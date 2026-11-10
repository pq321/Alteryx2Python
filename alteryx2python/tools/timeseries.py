"""Local implementations for Alteryx time-series, simulation and statistical tools.

The adapters deliberately operate on ordinary pandas frames and use scipy/statsmodels
only when the requested model needs them; unsupported options fail explicitly.
"""

from __future__ import annotations

from typing import Any, Callable
import numpy as np
import pandas as pd


def _frame(inputs):
    if not inputs:
        raise ValueError("Tool requires an input anchor")
    return next(iter(inputs.values()))


def _cfg(config):
    """Accept normalized dictionaries and common Designer Value/@name shapes."""
    out = dict(config or {})
    values = out.get("Value") or out.get("values")
    if isinstance(values, dict):
        for key, value in values.items():
            if key == "attributes" and isinstance(value, dict):
                out.update(value)
                continue
            if key == "text" and not isinstance(value, (dict, list)):
                out.setdefault("value", value)
                continue
            if isinstance(value, dict) and "@name" in value:
                out[value["@name"]] = value.get("#text", value.get("value"))
            else:
                out.setdefault(key, value)
    if isinstance(values, list):
        for value in values:
            if isinstance(value, dict) and ("@name" in value or "name" in value):
                name = value.get("@name", value.get("name"))
                out[name] = value.get("#text", value.get("value"))
    if isinstance(out.get("attributes"), dict):
        out.update(out["attributes"])
    if "text" in out and "value" not in out:
        out["value"] = out["text"]
    return out


def _col(df, config, key="value"):
    config = _cfg(config)
    name = config.get(key) or config.get("target_field") or config.get("value_field")
    if name is None:
        name = df.select_dtypes(include=np.number).columns[0]
    if name not in df:
        raise KeyError(f"Field not found: {name}")
    return name


def _out(df, values, name):
    result = df.copy()
    result[name] = values
    return {"Output": result}


def _forecast(inputs, config, kind="arima"):
    config = _cfg(config)
    df = _frame(inputs)
    field = _col(df, config)
    y = pd.to_numeric(df[field], errors="raise").dropna().to_numpy(float)
    h = int(config.get("horizon", config.get("forecast_periods", 1)))
    h = max(h, 1)
    if kind == "arima":
        from statsmodels.tsa.arima.model import ARIMA

        order = tuple(int(config.get(k, 0)) for k in ("p", "d", "q"))
        model = ARIMA(y, order=order).fit()
        pred = model.forecast(h)
    elif kind == "ets":
        from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing

        trend = config.get("trend") or None
        seasonal = config.get("seasonal") or None
        if seasonal and not config.get("seasonal_periods"):
            raise ValueError("seasonal_periods is required for seasonal ETS")
        cls = ExponentialSmoothing if trend or seasonal else SimpleExpSmoothing
        kw = (
            {"trend": trend, "seasonal": seasonal}
            if cls is ExponentialSmoothing
            else {}
        )
        if seasonal:
            kw["seasonal_periods"] = int(config["seasonal_periods"])
        pred = cls(y, **kw).fit(optimized=True).forecast(h)
    else:
        pred = np.repeat(y[-1], h)
    return pd.DataFrame(
        {"Forecast": np.asarray(pred, dtype=float), "Step": np.arange(1, h + 1)}
    )


def arima_tool(inputs, config, context=None):
    return {"Output": _forecast(inputs, config, "arima")}


def ets_tool(inputs, config, context=None):
    return {"Output": _forecast(inputs, config, "ets")}


def tsforecast_tool(inputs, config, context=None):
    return {"Output": _forecast(inputs, config, "arima")}


def tsmodel_factory_tool(inputs, config, context=None):
    import pickle

    config = _cfg(config)
    df = _frame(inputs)
    field = _col(df, config)
    y = pd.to_numeric(df[field], errors="raise").dropna().to_numpy(float)
    from statsmodels.tsa.arima.model import ARIMA

    order = tuple(int(config.get(k, 0)) for k in ("p", "d", "q"))
    fit = ARIMA(y, order=order).fit()
    return {
        "Model": pd.DataFrame(
            {
                "model_blob": [
                    pickle.dumps({"kind": "ARIMA", "order": order, "fit": fit})
                ]
            }
        ),
        "Output": pd.DataFrame({"AIC": [fit.aic], "BIC": [fit.bic]}),
    }


def tsforecast_factory_tool(inputs, config, context=None):
    import pickle

    config = _cfg(config)
    artifact = config.get("model") or config.get("Model")
    if artifact is None:
        artifact = inputs.get("Model")
    if isinstance(artifact, pd.DataFrame) and "model_blob" in artifact:
        artifact = artifact.iloc[0]["model_blob"]
    if not isinstance(artifact, (bytes, bytearray)):
        raise ValueError(
            "TSForecastFactory requires a local TSModelFactory model artifact"
        )
    model = pickle.loads(artifact).get("fit")
    h = int(config.get("horizon", 1))
    return {
        "Output": pd.DataFrame(
            {"Forecast": model.forecast(h), "Step": np.arange(1, h + 1)}
        )
    }


def tscovariateforecast_tool(inputs, config, context=None):
    config = _cfg(config)
    df = _frame(inputs)
    field = _col(df, config)
    cols = list(config.get("covariates") or config.get("exog") or [])
    if not cols:
        raise ValueError("TSCovariateForecast requires explicit covariates")
    if any(c not in df for c in cols):
        raise KeyError("Covariate fields not found")
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    fit = SARIMAX(
        pd.to_numeric(df[field]),
        exog=df[cols],
        order=tuple(int(config.get(k, 0)) for k in ("p", "d", "q")),
    ).fit(disp=False)
    future = config.get("future_covariates")
    if future is None:
        raise ValueError("future_covariates is required")
    h = len(future)
    pred = fit.forecast(h, exog=np.asarray(future, dtype=float))
    return {"Output": pd.DataFrame({"Forecast": pred, "Step": np.arange(1, h + 1)})}


def tsfiller_tool(inputs, config, context=None):
    config = _cfg(config)
    df = _frame(inputs).copy()
    field = _col(df, config)
    method = str(config.get("method", "linear")).lower()
    if method not in {"linear", "ffill", "bfill", "mean", "zero"}:
        raise ValueError(f"Unsupported TSFiller method: {method}")
    if method == "linear":
        df[field] = df[field].interpolate().ffill().bfill()
    elif method == "mean":
        df[field] = df[field].fillna(df[field].mean())
    elif method == "zero":
        df[field] = df[field].fillna(0)
    else:
        df[field] = getattr(df[field], method)()
    return {"Output": df}


def tscompare_tool(inputs, config, context=None):
    config = _cfg(config)
    df = _frame(inputs)
    a = config.get("actual_field") or _col(df, config)
    p = config.get("predicted_field") or config.get("forecast_field")
    if p not in df:
        raise KeyError(f"Field not found: {p}")
    e = pd.to_numeric(df[a]) - pd.to_numeric(df[p])
    return {
        "Output": pd.DataFrame(
            {
                "MAE": [e.abs().mean()],
                "RMSE": [np.sqrt((e**2).mean())],
                "MAPE": [
                    (e.abs() / pd.to_numeric(df[a]).replace(0, np.nan)).mean() * 100
                ],
            }
        )
    }


def tsplot_tool(inputs, config, context=None):
    config = _cfg(config)
    import matplotlib.pyplot as plt

    df = _frame(inputs)
    field = _col(df, config)
    ax = df[field].plot()
    fig = ax.get_figure()
    return {"Output": df, "Plot": pd.DataFrame({"figure": [fig]})}


def simulation_sampling_tool(inputs, config, context=None):
    config = _cfg(config)
    n = int(config.get("samples", config.get("n", 1000)))
    seed = config.get("seed")
    rng = np.random.default_rng(seed)
    dist = str(config.get("distribution", "normal")).lower()
    if dist == "normal":
        x = rng.normal(float(config.get("mean", 0)), float(config.get("std", 1)), n)
    elif dist == "uniform":
        x = rng.uniform(float(config.get("low", 0)), float(config.get("high", 1)), n)
    elif dist == "poisson":
        x = rng.poisson(float(config.get("lambda", 1)), n)
    else:
        raise ValueError(f"Unsupported simulation distribution: {dist}")
    return {"Output": pd.DataFrame({"Sample": x})}


def simulation_scoring_tool(inputs, config, context=None):
    config = _cfg(config)
    df = _frame(inputs)
    field = _col(df, config)
    threshold = float(config.get("threshold", 0))
    return {
        "Output": df.assign(
            Score=pd.to_numeric(df[field]),
            Success=pd.to_numeric(df[field]) >= threshold,
        )
    }


def simulation_summary_tool(inputs, config, context=None):
    config = _cfg(config)
    df = _frame(inputs)
    field = _col(df, config)
    s = pd.to_numeric(df[field])
    return {
        "Output": pd.DataFrame(
            {
                "Count": [s.count()],
                "Mean": [s.mean()],
                "StdDev": [s.std(ddof=1)],
                "Min": [s.min()],
                "Max": [s.max()],
            }
        )
    }


def optimization_tool(inputs, config, context=None):
    config = _cfg(config)
    if not config.get("c"):
        raise NotImplementedError(
            "Optimization requires explicit local LP coefficients 'c'"
        )
    from scipy.optimize import linprog

    c = np.asarray(config["c"], dtype=float).reshape(-1)
    if c.size == 0 or not np.all(np.isfinite(c)):
        raise ValueError("Optimization coefficients must be finite and non-empty")

    def matrix(key, cols):
        value = config.get(key)
        if value is None:
            return None
        a = np.asarray(value, dtype=float)
        if a.ndim != 2 or a.shape[1] != c.size:
            raise ValueError(f"{key} must have {c.size} columns")
        return a

    A_ub = matrix("A_ub", "c")
    b_ub = np.asarray(config.get("b_ub", []), dtype=float)
    if A_ub is not None and b_ub.size != A_ub.shape[0]:
        raise ValueError("b_ub length must match A_ub rows")
    A_eq = matrix("A_eq", "c")
    b_eq = np.asarray(config.get("b_eq", []), dtype=float)
    if A_eq is not None and b_eq.size != A_eq.shape[0]:
        raise ValueError("b_eq length must match A_eq rows")
    bounds = config.get("bounds", [(0, None)] * c.size)
    if len(bounds) != c.size:
        raise ValueError("bounds length must match c")
    if str(config.get("sense", "minimize")).lower() in {"max", "maximize"}:
        c = -c
    r = linprog(
        c,
        A_ub=A_ub,
        b_ub=b_ub if A_ub is not None else None,
        A_eq=A_eq,
        b_eq=b_eq if A_eq is not None else None,
        bounds=bounds,
        method="highs",
    )
    if not r.success:
        return {
            "Output": pd.DataFrame(
                {"Status": [r.status], "Success": [False], "Message": [r.message]}
            )
        }
    objective = float(np.dot(np.asarray(config.get("c"), dtype=float), r.x))
    return {
        "Output": pd.DataFrame(
            {
                "Variable": np.arange(c.size),
                "Value": r.x,
                "Objective": [objective] + [np.nan] * (c.size - 1),
                "Success": [True] + [None] * (c.size - 1),
            }
        )
    }


def count_regression_tool(inputs, config, context=None):
    config = _cfg(config)
    from statsmodels.api import GLM, families, add_constant

    df = _frame(inputs)
    y = _col(df, config)
    xs = config.get("predictors") or [
        c for c in df.select_dtypes(include=np.number).columns if c != y
    ]
    fit = GLM(df[y], add_constant(df[xs]), family=families.Poisson()).fit()
    return {
        "Output": pd.DataFrame(
            {"Field": fit.params.index, "Coefficient": fit.params.values}
        )
    }


def gamma_regression_tool(inputs, config, context=None):
    config = _cfg(config)
    from statsmodels.api import GLM, families, add_constant

    df = _frame(inputs)
    y = _col(df, config)
    xs = config.get("predictors") or [
        c for c in df.select_dtypes(include=np.number).columns if c != y
    ]
    fit = GLM(df[y], add_constant(df[xs]), family=families.Gamma()).fit()
    return {
        "Output": pd.DataFrame(
            {"Field": fit.params.index, "Coefficient": fit.params.values}
        )
    }


def test_of_means_tool(inputs, config, context=None):
    config = _cfg(config)
    from scipy import stats

    df = _frame(inputs)
    field = _col(df, config)
    x = pd.to_numeric(df[field]).dropna()
    pop = config.get("population_mean")
    r = stats.ttest_1samp(x, float(pop)) if pop is not None else stats.ttest_1samp(x, 0)
    return {"Output": pd.DataFrame({"Statistic": [r.statistic], "PValue": [r.pvalue]})}


def variance_inflation_factors_tool(inputs, config, context=None):
    config = _cfg(config)
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from statsmodels.api import add_constant

    df = _frame(inputs)
    cols = list(config.get("fields") or df.select_dtypes(include=np.number).columns)
    X = add_constant(df[cols], has_constant="add")
    return {
        "Output": pd.DataFrame(
            {
                "Field": cols,
                "VIF": [
                    variance_inflation_factor(X.values, i + 1) for i in range(len(cols))
                ],
            }
        )
    }


IMPLEMENTATIONS = {
    "ARIMA": arima_tool,
    "ETS": ets_tool,
    "TSForecast": tsforecast_tool,
    "TSFiller": tsfiller_tool,
    "TSCompare": tscompare_tool,
    "TSPlot": tsplot_tool,
    "TSCovariateForecast": tscovariateforecast_tool,
    "TSForecastFactory": tsforecast_factory_tool,
    "TSModelFactory": tsmodel_factory_tool,
    "SimulationSampling": simulation_sampling_tool,
    "SimulationScoring": simulation_scoring_tool,
    "SimulationSummary": simulation_summary_tool,
    "Optimization": optimization_tool,
    "CountRegression": count_regression_tool,
    "GammaRegression": gamma_regression_tool,
    "TestOfMeans": test_of_means_tool,
    "VarianceInflationFactors": variance_inflation_factors_tool,
}
ANCHORS = {k: (("Input",), ("Output",)) for k in IMPLEMENTATIONS}
ANCHORS["TSModelFactory"] = (("Input",), ("Model", "Output"))
ANCHORS["TSForecastFactory"] = (("Model",), ("Output",))
ANCHORS["SimulationSampling"] = ((), ("Output",))
PARSERS = {}


def _recording(name, fn):
    def call(inputs, config, context=None):
        outputs = fn(inputs, config, context)
        if context is not None and hasattr(context, "record_node"):
            frames = {k: v for k, v in outputs.items() if isinstance(v, pd.DataFrame)}
            context.record_node(
                node_id=str((config or {}).get("node_id", "unknown")),
                tool_type=name,
                source_tool_id=(config or {}).get("source_tool_id") or name,
                inputs=inputs,
                outputs=frames,
                status="success",
                config=dict(config or {}),
            )
        return outputs

    return call


for _name, _fn in list(IMPLEMENTATIONS.items()):
    IMPLEMENTATIONS[_name] = _recording(_name, _fn)
