from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _ordered_inputs(inputs: dict[str, pd.DataFrame]) -> list[tuple[str, pd.DataFrame]]:
    return sorted(inputs.items(), key=lambda item: (item[0] != "Input", item[0]))


def _connection_name(index: int) -> str:
    return f"#{index}"


def _join_fields(config: dict[str, Any], connection: str) -> list[str]:
    for join in config.get("joins", []):
        if isinstance(join, dict) and str(join.get("connection")) == connection:
            return [str(field) for field in join.get("fields", [])]
    return []


def _prefix_frame(frame: pd.DataFrame, connection: str) -> pd.DataFrame:
    return frame.rename(columns={column: f"Input_{connection}_{column}" for column in frame.columns})


def _join_by_position(frames: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    pieces = []
    for index, (_, frame) in enumerate(frames, start=1):
        pieces.append(_prefix_frame(frame.reset_index(drop=True), _connection_name(index)))
    return pd.concat(pieces, axis=1)


def _join_by_fields(frames: list[tuple[str, pd.DataFrame]], config: dict[str, Any]) -> pd.DataFrame:
    prepared = []
    for index, (_, frame) in enumerate(frames, start=1):
        connection = _connection_name(index)
        fields = _join_fields(config, connection)
        if not fields:
            raise ValueError(f"JoinMultiple config requires join fields for {connection}")
        ensure_fields_exist(frame, fields)
        prefixed = _prefix_frame(frame.reset_index(drop=True), connection)
        left_keys = [f"Input_{connection}_{field}" for field in fields]
        prepared.append((connection, prefixed, left_keys))

    result = prepared[0][1]
    result_keys = prepared[0][2]
    for connection, frame, keys in prepared[1:]:
        result = result.merge(frame, how="inner", left_on=result_keys, right_on=keys)
    return result


def _apply_select(joined: pd.DataFrame, select_fields: list[dict[str, Any]]) -> pd.DataFrame:
    if not select_fields:
        return joined
    output = joined.copy()
    for field in select_fields:
        source = str(field.get("source", ""))
        if source == "*Unknown":
            continue
        if source not in output.columns or not field.get("selected", True):
            continue
        rename = str(field.get("rename", source))
        if rename != source:
            output = output.rename(columns={source: rename})
    return output


def joinmultiple_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if len(inputs) < 2:
        raise KeyError("JoinMultiple requires at least two input anchors")
    frames = _ordered_inputs(inputs)
    for _, frame in frames:
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("JoinMultiple inputs must be pandas DataFrames")

    if bool(config.get("join_by_record_position", False)):
        joined = _join_by_position(frames)
    else:
        joined = _join_by_fields(frames, config)
    output = _apply_select(joined, [field for field in config.get("select_fields", []) if isinstance(field, dict)])

    outputs = {"Output": output.reset_index(drop=True)}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="JoinMultiple",
        source_tool_id=config.get("source_tool_id"),
        inputs=dict(frames),
        outputs=outputs,
        status="success",
        config={
            "join_by_record_position": bool(config.get("join_by_record_position", False)),
            "input_schema": {anchor: snapshot_schema(frame) for anchor, frame in frames},
            "output_schema": snapshot_schema(outputs["Output"]),
        },
    )
    return outputs


class JoinMultipleTool(BaseTool):
    tool_type = "JoinMultiple"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return joinmultiple_tool(inputs, config, context)
