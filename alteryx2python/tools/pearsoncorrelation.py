from __future__ import annotations

from itertools import combinations
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("PearsonCorrelation tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _is_numeric_column(series: pd.Series) -> bool:
    converted = pd.to_numeric(series, errors="coerce")
    return bool(converted.notna().all())


def _expand_fields(frame: pd.DataFrame, fields: list[str]) -> list[str]:
    selected: list[str] = []
    wildcard_selected = False
    for field in fields:
        if field == "*Unknown":
            wildcard_selected = True
            continue
        selected.append(field)
    ensure_fields_exist(frame, selected)
    if wildcard_selected:
        for column in frame.columns:
            if column not in selected and _is_numeric_column(frame[column]):
                selected.append(column)
    return selected


def _numeric_frame(frame: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    selected = frame.loc[:, fields].apply(pd.to_numeric, errors="coerce")
    if selected.isna().any().any():
        raise ValueError("PearsonCorrelation requires selected fields to be numeric and non-null")
    return selected


def _pair_rows(data: pd.DataFrame, covariance: bool) -> list[dict[str, Any]]:
    correlations = data.corr(method="pearson")
    covariances = data.cov() if covariance else None
    rows: list[dict[str, Any]] = []
    for field_1, field_2 in combinations(data.columns, 2):
        row = {
            "Field1": field_1,
            "Field2": field_2,
            "Correlation": correlations.loc[field_1, field_2],
        }
        if covariances is not None:
            row["Covariance"] = covariances.loc[field_1, field_2]
        rows.append(row)
    return rows


def pearsoncorrelation_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    fields = _expand_fields(input_frame, [str(field) for field in config.get("fields", [])])
    if len(fields) < 2:
        raise ValueError("PearsonCorrelation requires at least two selected fields")

    covariance = bool(config.get("covariance", False))
    numeric = _numeric_frame(input_frame, fields)
    output = pd.DataFrame(_pair_rows(numeric, covariance))
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="PearsonCorrelation",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "fields": fields,
            "covariance": covariance,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class PearsonCorrelationTool(BaseTool):
    tool_type = "PearsonCorrelation"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return pearsoncorrelation_tool(inputs, config, context)
