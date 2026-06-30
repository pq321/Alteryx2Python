from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


SPATIAL_ACTIONS = {"SpatialObjCombine", "SpatialObjConvexHull"}


def _is_blank(value: Any) -> bool:
    return pd.isna(value) or value == ""


def _longest(series: pd.Series) -> Any:
    values = series.dropna().astype(str)
    return "" if values.empty else values.loc[values.map(len).idxmax()]


def _shortest(series: pd.Series) -> Any:
    values = series.dropna().astype(str)
    return "" if values.empty else values.loc[values.map(len).idxmin()]


def _mode(series: pd.Series) -> Any:
    values = series.dropna()
    if values.empty:
        return None
    modes = values.mode()
    return None if modes.empty else modes.iloc[0]


def _concat(series: pd.Series, field_config: dict[str, Any]) -> str:
    values = ["" if pd.isna(value) else str(value) for value in series.tolist()]
    return f"{field_config.get('concat_start', '')}{field_config.get('separator', '').join(values)}{field_config.get('concat_end', '')}"


def _aggregate(series: pd.Series, field_config: dict[str, Any]) -> Any:
    action = str(field_config.get("action", ""))
    if action in SPATIAL_ACTIONS:
        raise NotImplementedError(f"Summarize action is deferred: {action}")
    if action == "Sum":
        return pd.to_numeric(series, errors="coerce").sum()
    if action == "Count":
        return int(len(series.index))
    if action == "CountNonBlank":
        return int((~series.map(_is_blank)).sum())
    if action == "CountBlank":
        return int(series.map(_is_blank).sum())
    if action == "Min":
        return series.min()
    if action == "Max":
        return series.max()
    if action == "Avg":
        return pd.to_numeric(series, errors="coerce").mean()
    if action == "Median":
        return pd.to_numeric(series, errors="coerce").median()
    if action == "Mode":
        return _mode(series)
    if action == "StdDev":
        return pd.to_numeric(series, errors="coerce").std()
    if action == "Variance":
        return pd.to_numeric(series, errors="coerce").var()
    if action == "First":
        return series.iloc[0] if len(series.index) else None
    if action == "Last":
        return series.iloc[-1] if len(series.index) else None
    if action == "Longest":
        return _longest(series)
    if action == "Shortest":
        return _shortest(series)
    if action == "Concat":
        return _concat(series, field_config)
    raise NotImplementedError(f"Summarize action is not supported: {action}")


def _summarize_group(group: pd.DataFrame, fields: list[dict[str, Any]], group_fields: list[dict[str, Any]]) -> dict[str, Any]:
    row = {str(field.get("rename") or field.get("field")): group.iloc[0][str(field["field"])] for field in group_fields}
    for field in fields:
        if field in group_fields:
            continue
        source = str(field.get("field", ""))
        row[str(field.get("rename") or source)] = _aggregate(group[source], field)
    return row


def summarize_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Summarize tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    fields = [field for field in config.get("summarize_fields", []) if isinstance(field, dict)]
    if not fields:
        raise ValueError("Summarize config requires summarize_fields")
    ensure_fields_exist(input_frame, [str(field.get("field", "")) for field in fields])

    group_fields = [field for field in fields if field.get("action") == "GroupBy"]
    if group_fields:
        group_names = [str(field["field"]) for field in group_fields]
        rows = [
            _summarize_group(group, fields, group_fields)
            for _, group in input_frame.groupby(group_names, sort=False, dropna=False)
        ]
    else:
        rows = [_summarize_group(input_frame, fields, [])]
    output = pd.DataFrame(rows)

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Summarize",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "summarize_fields": fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class SummarizeTool(BaseTool):
    tool_type = "Summarize"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return summarize_tool(inputs, config, context)
