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
        output = _selected_output(joined, select_fields, left.columns, right.columns, config.get("order_changed", True))
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
