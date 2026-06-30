from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _equal_records(frame: pd.DataFrame, num_tiles: int) -> pd.Series:
    if len(frame.index) == 0:
        return pd.Series(dtype="Int64")
    return (pd.Series(range(len(frame.index)), index=frame.index) * num_tiles // len(frame.index) + 1).clip(upper=num_tiles)


def _equal_sum(frame: pd.DataFrame, field: str, num_tiles: int) -> pd.Series:
    values = pd.to_numeric(frame[field], errors="coerce").fillna(0)
    total = values.sum()
    if total == 0:
        return _equal_records(frame, num_tiles)
    cumulative = values.cumsum()
    return ((cumulative - 1e-12) / (total / num_tiles)).astype(int).clip(upper=num_tiles - 1) + 1


def _manual(frame: pd.DataFrame, field: str, cutoffs: list[float]) -> pd.Series:
    values = pd.to_numeric(frame[field], errors="coerce")
    bins = [-float("inf"), *cutoffs, float("inf")]
    return pd.cut(values, bins=bins, labels=False, include_lowest=True).astype("Int64") + 1


def _unique_value(frame: pd.DataFrame, fields: list[str], dont_sort: bool) -> pd.Series:
    keys = frame[fields].astype(str).agg("\x1f".join, axis=1)
    uniques = list(dict.fromkeys(keys if dont_sort else sorted(keys.unique())))
    mapping = {value: index + 1 for index, value in enumerate(uniques)}
    return keys.map(mapping).astype("Int64")


def _tile_group(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    method = str(config.get("method", "EqualRecords"))
    output = frame.copy()
    if method == "EqualRecords":
        sort_field = str(config.get("sort_field") or "")
        if sort_field:
            ensure_fields_exist(output, [sort_field])
            output = output.sort_values(sort_field, kind="mergesort")
        output["Tile_Num"] = _equal_records(output, int(config.get("num_tiles", 1))).astype("Int64")
    elif method == "EqualSum":
        field = str(config.get("sum_field", ""))
        ensure_fields_exist(output, [field])
        output = output.sort_values(field, kind="mergesort")
        output["Tile_Num"] = _equal_sum(output, field, int(config.get("num_tiles", 1))).astype("Int64")
    elif method == "Manual":
        field = str(config.get("field", ""))
        ensure_fields_exist(output, [field])
        output["Tile_Num"] = _manual(output, field, [float(value) for value in config.get("cutoffs", [])])
    elif method == "UniqueValue":
        fields = [str(field) for field in config.get("unique_fields", [])]
        ensure_fields_exist(output, fields)
        output["Tile_Num"] = _unique_value(output, fields, bool(config.get("dont_sort", False)))
    elif method == "SmartTile":
        field = str(config.get("field", ""))
        ensure_fields_exist(output, [field])
        output = output.sort_values(field, kind="mergesort")
        output["Tile_Num"] = _equal_records(output, 5).astype("Int64")
        output[str(config.get("name_field", "Tile_Name"))] = "Tile " + output["Tile_Num"].astype(str)
    else:
        raise NotImplementedError(f"Tile method is not supported: {method}")
    return output


def tile_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Tile tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    group_fields = [str(field) for field in config.get("group_fields", [])]
    ensure_fields_exist(input_frame, group_fields)

    if group_fields:
        pieces = [
            _tile_group(group.reset_index(drop=True), config)
            for _, group in input_frame.groupby(group_fields, sort=False, dropna=False)
        ]
        output = pd.concat(pieces, ignore_index=True) if pieces else input_frame.iloc[0:0].copy()
    else:
        output = _tile_group(input_frame.reset_index(drop=True), config)

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Tile",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "method": config.get("method", "EqualRecords"),
            "group_fields": group_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class TileTool(BaseTool):
    tool_type = "Tile"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return tile_tool(inputs, config, context)
