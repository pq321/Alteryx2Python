from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


RANK_METHODS = {
    "Ordinal": "first",
    "Dense": "dense",
    "Standard": "min",
    "Competition": "min",
    "Fractional": "average",
}


def _rank_series(frame: pd.DataFrame, sort_field: str, ascending: bool, mode: str, group_fields: list[str]) -> pd.Series:
    method = RANK_METHODS.get(mode, "first")
    values = pd.to_numeric(frame[sort_field], errors="coerce")
    if group_fields:
        return values.groupby([frame[field] for field in group_fields], sort=False).rank(method=method, ascending=ascending)
    return values.rank(method=method, ascending=ascending)


def rank_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Rank tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    sort_fields = [field for field in config.get("sort_fields", []) if isinstance(field, dict)]
    if not sort_fields:
        raise ValueError("Rank config requires sort_fields")
    group_fields = [str(field) for field in config.get("group_fields", [])]
    ranking_modes = [str(mode) for mode in config.get("ranking_modes", ["Ordinal"])]
    ensure_fields_exist(input_frame, [*group_fields, *[str(field.get("field", "")) for field in sort_fields]])

    by = [str(field["field"]) for field in sort_fields]
    ascending = [str(field.get("order", "Ascending")).lower() != "descending" for field in sort_fields]
    output = input_frame.sort_values(by=by, ascending=ascending, kind="mergesort").reset_index(drop=True)
    primary_sort = by[0]
    primary_ascending = ascending[0]
    for mode in ranking_modes:
        column = "Rank" if len(ranking_modes) == 1 else f"Rank_{mode}"
        output[column] = _rank_series(output, primary_sort, primary_ascending, mode, group_fields).astype("Float64")
        if mode in {"Ordinal", "Dense", "Standard", "Competition"}:
            output[column] = output[column].astype("Int64")

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Rank",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "ranking_modes": ranking_modes,
            "sort_fields": sort_fields,
            "group_fields": group_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class RankTool(BaseTool):
    tool_type = "Rank"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return rank_tool(inputs, config, context)
