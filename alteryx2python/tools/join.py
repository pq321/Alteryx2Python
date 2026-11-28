from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


from alteryx2python.tools.sort import sort_binary_frame


def join_keys(config, connection):
    return [str(join["field"]) for join in config.get("joins", [])
            if isinstance(join, dict) and join.get("connection") == connection and join.get("field")]


def _prefix_frame(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    return frame.rename(columns={column: f"{prefix}_{column}" for column in frame.columns})


def _selected_output(joined, select_fields, left_columns, right_columns, order_changed):
    fields = {field["source"]: field for field in select_fields}
    include_unknown = fields.get("*Unknown", {}).get("selected", False)
    default_names = {f"Left_{name}": name for name in left_columns}
    default_names.update({
        f"Right_{name}": f"Right_{name}" if name in left_columns else name
        for name in right_columns
    })
    selected = []
    for source in fields if order_changed else joined.columns:
        if source == "*Unknown":
            if include_unknown:
                selected.extend((name, default_names[name]) for name in joined if name not in fields)
        elif source in fields:
            field = fields[source]
            if field.get("selected", True) and source in joined:
                selected.append((source, field.get("rename", default_names[source])))
        elif include_unknown:
            selected.append((source, default_names[source]))
    result = joined[[source for source, _ in selected]].copy()
    result.columns = [name for _, name in selected]
    return result


def join_frames(left, right, left_keys, right_keys, fields, order_changed, by_position):
    if not by_position and (not left_keys or len(left_keys) != len(right_keys)):
        raise ValueError("Join requires equally many Left and Right fields")
    ensure_fields_exist(left, left_keys)
    ensure_fields_exist(right, right_keys)
    left_indexed = _prefix_frame(left.reset_index(drop=True), "Left")
    right_indexed = _prefix_frame(right.reset_index(drop=True), "Right")
    left_indexed["__left_index"] = range(len(left))
    right_indexed["__right_index"] = range(len(right))
    merged = left_indexed.merge(
        right_indexed,
        how="inner",
        left_on=["__left_index"] if by_position else [f"Left_{key}" for key in left_keys],
        right_on=["__right_index"] if by_position else [f"Right_{key}" for key in right_keys],
        sort=True,  # Original engine emits key-sorted groups (native SortInfo).
    )
    if not by_position:
        # Classic sorts keys, including nulls before empty strings.
        order = [f"Left_{key}" for key in left_keys] + ["__right_index", "__left_index"]
        merged = sort_binary_frame(merged, order, [True] * len(order))
    left_matched = set(merged["__left_index"].tolist())
    right_matched = set(merged["__right_index"].tolist())

    left_prefixed = merged[[f"Left_{column}" for column in left.columns]]
    right_prefixed = merged[[f"Right_{column}" for column in right.columns]]
    joined = pd.concat([left_prefixed, right_prefixed], axis=1)
    if fields:
        output = _selected_output(joined, fields, left.columns, right.columns, order_changed)
    else:
        output = joined
    return (output.reset_index(drop=True),
            left.iloc[[idx for idx in range(len(left)) if idx not in left_matched]].reset_index(drop=True),
            right.iloc[[idx for idx in range(len(right)) if idx not in right_matched]].reset_index(drop=True))


def join_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Left" not in inputs or "Right" not in inputs:
        raise KeyError("Join tool requires Left and Right anchors")
    left, right = inputs["Left"], inputs["Right"]
    by_position = config.get("join_by_record_pos", False)
    left_keys = [] if by_position else join_keys(config, "Left")
    right_keys = [] if by_position else join_keys(config, "Right")
    fields = [field for field in config.get("select_fields", []) if isinstance(field, dict)]
    outputs = dict(zip(("Join", "Left", "Right"), join_frames(
        left, right, left_keys, right_keys, fields, config.get("order_changed", True), by_position
    )))
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Join",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Left": left, "Right": right},
        outputs=outputs,
        status="success",
        config={
            "left_field": left_keys[0] if left_keys else "",
            "right_field": right_keys[0] if right_keys else "",
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
