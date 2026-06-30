from __future__ import annotations

import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _delimiter_pattern(delimiters: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(delimiters):
        if delimiters[index:index + 2] == r"\s":
            parts.append(r"\s")
            index += 2
        else:
            parts.append(re.escape(delimiters[index]))
            index += 1
    return f"[{''.join(parts)}]+"


def _split_value(value: Any, delimiters: str) -> list[str]:
    text = "" if pd.isna(value) else str(value)
    if delimiters == "":
        return [text]
    return re.split(_delimiter_pattern(delimiters), text)


def _column_names(root_name: str, count: int) -> list[str]:
    return [f"{root_name}{index}" for index in range(1, count + 1)]


def _split_to_columns(input_frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    field = str(config.get("field", ""))
    root_name = str(config.get("root_name", field))
    num_fields = int(config.get("num_fields", 1))
    delimiters = str(config.get("delimiters", ""))
    error_handling = str(config.get("error_handling", "Last"))
    output = input_frame.copy()
    names = _column_names(root_name, num_fields)
    values_by_column = {name: [] for name in names}

    for value in input_frame[field].tolist():
        parts = _split_value(value, delimiters)
        if len(parts) > num_fields and error_handling.lower() == "last":
            parts = [*parts[: num_fields - 1], delimiters[:1].join(parts[num_fields - 1:])]
        padded = [*parts[:num_fields], *([""] * max(0, num_fields - len(parts)))]
        for name, part in zip(names, padded):
            values_by_column[name].append(part)
    for name in names:
        output[name] = values_by_column[name]
    return output


def _split_to_rows(input_frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    field = str(config.get("field", ""))
    delimiters = str(config.get("delimiters", ""))
    rows: list[dict[str, Any]] = []
    for row in input_frame.to_dict("records"):
        parts = _split_value(row[field], delimiters)
        for part in parts:
            next_row = dict(row)
            next_row[field] = part
            rows.append(next_row)
    return pd.DataFrame(rows, columns=input_frame.columns)


def texttocolumns_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("TextToColumns tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    field = str(config.get("field", ""))
    ensure_fields_exist(input_frame, [field])

    flags = int(config.get("flags", 0))
    output = _split_to_rows(input_frame, config) if flags & 1 else _split_to_columns(input_frame, config)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="TextToColumns",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "field": field,
            "root_name": config.get("root_name", field),
            "delimiters": config.get("delimiters", ""),
            "num_fields": config.get("num_fields", 1),
            "flags": flags,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class TextToColumnsTool(BaseTool):
    tool_type = "TextToColumns"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return texttocolumns_tool(inputs, config, context)
