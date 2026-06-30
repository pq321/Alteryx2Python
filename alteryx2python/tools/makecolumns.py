from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _reshape_group(frame: pd.DataFrame, num_columns: int, is_horizontal: bool) -> pd.DataFrame:
    rows = frame.to_dict("records")
    if not rows:
        return frame.iloc[0:0].copy()
    output_rows = []
    for offset in range(0, len(rows), num_columns):
        chunk = rows[offset : offset + num_columns]
        combined: dict[str, Any] = {}
        ordered = chunk if is_horizontal else chunk
        for index, record in enumerate(ordered, start=1):
            for column, value in record.items():
                combined[f"{column}_{index}"] = value
        output_rows.append(combined)
    return pd.DataFrame(output_rows)


def makecolumns_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("MakeColumns tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    num_columns = int(config.get("num_columns", 1))
    if num_columns <= 0:
        raise ValueError("MakeColumns num_columns must be positive")
    is_horizontal = bool(config.get("is_horizontal", True))
    group_fields = [str(field) for field in config.get("group_fields", [])]
    ensure_fields_exist(input_frame, group_fields)

    if group_fields:
        pieces = [
            _reshape_group(group.reset_index(drop=True), num_columns, is_horizontal)
            for _, group in input_frame.groupby(group_fields, sort=False, dropna=False)
        ]
        output = pd.concat(pieces, ignore_index=True) if pieces else input_frame.iloc[0:0].copy()
    else:
        output = _reshape_group(input_frame.reset_index(drop=True), num_columns, is_horizontal)
    output = output.astype(object).where(pd.notna(output), None)

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="MakeColumns",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "num_columns": num_columns,
            "is_horizontal": is_horizontal,
            "group_fields": group_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class MakeColumnsTool(BaseTool):
    tool_type = "MakeColumns"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return makecolumns_tool(inputs, config, context)
