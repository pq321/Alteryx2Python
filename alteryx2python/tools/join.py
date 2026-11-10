from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _join_field(config: dict[str, Any], connection: str) -> str:
    for join in config.get("joins", []):
        if isinstance(join, dict) and str(join.get("connection")) == connection:
            return str(join.get("field", ""))
    return ""


def _prefix_frame(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    return frame.rename(columns={column: f"{prefix}_{column}" for column in frame.columns})


def _selected_output(joined: pd.DataFrame, select_fields: list[dict[str, Any]]) -> pd.DataFrame:
    output_columns: dict[str, pd.Series] = {}
    for field in select_fields:
        if not field.get("selected", True):
            continue
        source = str(field.get("source", ""))
        if source == "*Unknown":
            continue
        rename = str(field.get("rename", source))
        output_columns[rename] = joined[source]
    return pd.DataFrame(output_columns, index=joined.index)


def join_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Left" not in inputs or "Right" not in inputs:
        raise KeyError("Join tool requires Left and Right anchors")
    left = inputs["Left"]
    right = inputs["Right"]
    left_field = _join_field(config, "Left")
    right_field = _join_field(config, "Right")
    if not left_field or not right_field:
        raise ValueError("Join config requires Left and Right join fields")
    ensure_fields_exist(left, [left_field])
    ensure_fields_exist(right, [right_field])

    left_indexed = _prefix_frame(left.reset_index(drop=True), "Left")
    right_indexed = _prefix_frame(right.reset_index(drop=True), "Right")
    left_indexed["__left_index"] = range(len(left))
    right_indexed["__right_index"] = range(len(right))
    merged = left_indexed.merge(
        right_indexed,
        how="inner",
        left_on=f"Left_{left_field}",
        right_on=f"Right_{right_field}",
        sort=True,  # Original engine emits key-sorted groups (native SortInfo).
    )
    left_matched = set(merged["__left_index"].tolist())
    right_matched = set(merged["__right_index"].tolist())

    left_prefixed = merged[[f"Left_{column}" for column in left.columns]]
    right_prefixed = merged[[f"Right_{column}" for column in right.columns]]
    joined = pd.concat([left_prefixed, right_prefixed], axis=1)
    select_fields = [field for field in config.get("select_fields", []) if isinstance(field, dict)]
    if select_fields:
        output = _selected_output(joined, select_fields)
    else:
        output = joined
    outputs = {
        "Join": output.reset_index(drop=True),
        "Left": left.iloc[[idx for idx in range(len(left)) if idx not in left_matched]].reset_index(drop=True),
        "Right": right.iloc[[idx for idx in range(len(right)) if idx not in right_matched]].reset_index(drop=True),
    }
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Join",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Left": left, "Right": right},
        outputs=outputs,
        status="success",
        config={
            "left_field": left_field,
            "right_field": right_field,
            "input_schema": {"Left": snapshot_schema(left), "Right": snapshot_schema(right)},
            "output_schema": {anchor: snapshot_schema(frame) for anchor, frame in outputs.items()},
        },
    )
    return outputs


class JoinTool(BaseTool):
    tool_type = "Join"
    input_anchors = ("Left", "Right")
    output_anchors = ("Join", "Left", "Right")

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return join_tool(inputs, config, context)
