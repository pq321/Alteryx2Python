from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


TYPE_MAP = {
    "Int16": "Int16",
    "Int32": "Int32",
    "Int64": "Int64",
}


def _sequence(length: int, start_value: int) -> pd.Series:
    return pd.Series(range(start_value, start_value + length), dtype="Int64")


def _grouped_sequence(frame: pd.DataFrame, group_fields: list[str], start_value: int) -> pd.Series:
    if not group_fields:
        return _sequence(len(frame.index), start_value)
    missing = [field for field in group_fields if field not in frame.columns]
    if missing:
        raise KeyError(f"Missing RecordID group fields: {', '.join(missing)}")
    values = pd.Series(index=frame.index, dtype="Int64")
    for _, group in frame.groupby(group_fields, sort=False, dropna=False):
        values.loc[group.index] = _sequence(len(group.index), start_value).to_numpy()
    return values.astype("Int64")


def recordid_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("RecordID tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    field_name = str(config.get("field_name", "RecordID"))
    start_value = int(config.get("start_value", 1))
    position = int(config.get("position", 0))
    field_type = str(config.get("field_type", "Int32"))
    group_fields = [str(field) for field in config.get("group_fields", [])]
    if field_type not in TYPE_MAP:
        raise ValueError(f"Unsupported RecordID field_type: {field_type}")

    output = input_frame.copy()
    values = _grouped_sequence(output, group_fields, start_value).astype(TYPE_MAP[field_type])
    values.index = output.index
    output[field_name] = values
    if position == 0:
        columns = [field_name] + [column for column in output.columns if column != field_name]
        output = output[columns]
    elif position != 1:
        raise ValueError("RecordID position supports 0 (first) or 1 (last)")

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="RecordID",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "field_name": field_name,
            "start_value": start_value,
            "field_type": field_type,
            "position": position,
            "group_fields": group_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class RecordIDTool(BaseTool):
    tool_type = "RecordID"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return recordid_tool(inputs, config, context)
