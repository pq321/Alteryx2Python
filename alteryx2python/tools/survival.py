"""Local survival analysis and mean-test adapters using statsmodels/scipy."""

from __future__ import annotations
import pickle
from typing import Any
import pandas as pd
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.comparison.schema_diff import snapshot_schema


def _deps():
    try:
        from scipy import stats
        from statsmodels.duration.hazard_regression import PHReg

        return stats, PHReg
    except ImportError as exc:
        raise RuntimeError("survival tools require scipy and statsmodels") from exc


def survival_tool(
    kind: str,
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if not isinstance(context, WorkflowContext) or not config.get("source_tool_id"):
        raise ValueError("survival tools require WorkflowContext and source_tool_id")
    frame = inputs.get("Input")
    if frame is None:
        frame = inputs.get("Data")
    if frame is None:
        raise KeyError("survival tool requires Input anchor")
    stats, PHReg = _deps()
    if kind == "TestofMeans":
        a = frame[config.get("sample_a", "A")].dropna()
        mode = config.get("mode", "independent")
        if mode == "paired":
            pair = frame[
                [config.get("sample_a", "A"), config.get("sample_b", "B")]
            ].dropna()
            result = stats.ttest_rel(pair.iloc[:, 0], pair.iloc[:, 1])
        elif mode == "one_sample":
            result = stats.ttest_1samp(a, float(config.get("popmean", 0.0)))
        elif mode == "independent":
            b = frame[config.get("sample_b", "B")].dropna()
            result = stats.ttest_ind(
                a, b, equal_var=bool(config.get("equal_var", False))
            )
        else:
            raise NotImplementedError(f"unsupported TestofMeans mode: {mode}")
        out = pd.DataFrame(
            {"Statistic": [float(result.statistic)], "PValue": [float(result.pvalue)]}
        )
        outputs = {"R": out}
    elif kind == "SurvivalAnalysis":
        duration, event = (
            config.get("duration_field", "Duration"),
            config.get("event_field", "Event"),
        )
        predictors = config.get("predictors") or [
            c for c in frame.columns if c not in (duration, event)
        ]
        missing = [c for c in [duration, event, *predictors] if c not in frame.columns]
        if missing:
            raise KeyError(f"missing survival fields: {missing}")
        model = PHReg(
            frame[duration],
            frame[predictors],
            status=frame[event],
            ties=config.get("ties", "breslow"),
        ).fit()
        artifact = pd.DataFrame(
            {
                "model_blob": [pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)],
                "predictors": [pickle.dumps(predictors)],
            }
        )
        outputs = {"O": artifact}
    elif kind == "SurvivalScore":
        model_frame = inputs.get("Model")
        if model_frame is None:
            model_frame = inputs.get("O")
        if model_frame is None or model_frame.empty or "model_blob" not in model_frame:
            raise ValueError("SurvivalScore requires fitted Model/O artifact")
        try:
            model = pickle.loads(model_frame.iloc[0]["model_blob"])
        except Exception as exc:
            raise ValueError("invalid survival model artifact") from exc
        predictors = pickle.loads(model_frame.iloc[0]["predictors"])
        missing = [c for c in predictors if c not in frame.columns]
        if missing:
            raise KeyError(f"missing survival score fields: {missing}")
        out = frame.copy()
        out[config.get("score_field", "RiskScore")] = model.predict(
            exog=out[predictors]
        ).predicted_values
        outputs = {"O": out}
    else:
        raise NotImplementedError(f"unsupported survival tool: {kind}")
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=kind,
        source_tool_id=str(config["source_tool_id"]),
        inputs=inputs,
        outputs=outputs,
        status="success",
        config={
            "input_schema": snapshot_schema(frame),
            "output_schema": {k: snapshot_schema(v) for k, v in outputs.items()},
            "model_representation": "local statsmodels/scipy; pickle artifacts are not native Alteryx bytes",
        },
    )
    return outputs


IMPLEMENTATIONS = {
    k: (
        lambda inputs, config, context, _k=k: survival_tool(_k, inputs, config, context)
    )
    for k in ("SurvivalAnalysis", "SurvivalScore", "TestofMeans")
}
ANCHORS = {
    "SurvivalAnalysis": (("Input",), ("O",)),
    "SurvivalScore": (("Input", "Model"), ("O",)),
    "TestofMeans": (("Input",), ("R",)),
}
PARSERS: dict[str, Any] = {}
