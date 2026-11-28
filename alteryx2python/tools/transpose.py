from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def transpose_frame(frame, key_fields, data_fields):
    text_types = {"string", "unicode"}
    as_text = any(pd.api.types.infer_dtype(frame[field], skipna=True) in text_types for field in data_fields)
    rows = []
    for source_row in frame.to_dict("records"):
        keys = [source_row[field] for field in key_fields]
        for field in data_fields:
            value = source_row[field]
            if as_text and not pd.isna(value):
                value = str(value)
            rows.append([*keys, field, value])
    return pd.DataFrame(rows, columns=[*key_fields, "Name", "Value"])


def transpose_fields(columns, keys, configured):
    selected = {field["field"]: field.get("selected", False) for field in configured if isinstance(field, dict)}
    keep_unknown = selected.get("*Unknown", False)
    return [column for column in columns if column not in keys and selected.get(column, keep_unknown)]


def transpose_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Transpose tool requires an Input anchor")
    input_frame = inputs["Input"]
    key_fields = list(config.get("key_fields", []))
    selected_data_fields = [
        field["field"]
        for field in config.get("data_fields", [])
        if isinstance(field, dict) and field.get("selected", False)
    ]
    selected_data_field_set = set(selected_data_fields)
    data_fields = [field for field in input_frame.columns if field in selected_data_field_set]
    ensure_fields_exist(input_frame, key_fields)
    missing_data_fields = [field for field in selected_data_fields if field not in input_frame.columns]
    if missing_data_fields and str(config.get("error_warn", "")).lower() != "warn":
        ensure_fields_exist(input_frame, missing_data_fields)

    rows: list[dict[str, Any]] = []
    for source_row in input_frame.to_dict("records"):
        key_values = {field: source_row[field] for field in key_fields}
        for field in data_fields:
            rows.append({**key_values, "Name": field, "Value": source_row[field]})
    output = pd.DataFrame(rows, columns=[*key_fields, "Name", "Value"])
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Transpose",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "key_fields": key_fields,
            "data_fields": data_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class TransposeTool(BaseTool):
    tool_type = "Transpose"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return transpose_tool(inputs, config, context)
