from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


SUPPORTED_TYPE_MAP = {
    "Bool": "boolean",
    "Byte": "UInt8",
    "Double": "float64",
    "FixedDecimal": "float64",
    "Float": "float32",
    "Int16": "Int16",
    "Int32": "Int32",
    "Int64": "Int64",
    "String": "string",
    "V_String": "string",
    "V_WString": "string",
    "WString": "string",
    "string": "string",
    "int64": "Int64",
    "float64": "float64",
    "bool": "boolean",
}


def _validate_inputs(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("Select tool requires an Input anchor")

    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    return frame


def _normalize_select_fields(config: dict[str, Any]) -> list[dict[str, Any]]:
    select_fields = config.get("select_fields")
    if not isinstance(select_fields, list) or not select_fields:
        raise ValueError("Select tool config requires a non-empty select_fields list")

    normalized: list[dict[str, Any]] = []
    for entry in select_fields:
        if not isinstance(entry, dict):
            raise TypeError("Each select_fields entry must be a dictionary")
        if "source" not in entry:
            raise ValueError("Each select_fields entry must define a source field")
        source = entry["source"]
        rename = entry.get("rename", source)
        dtype = entry.get("dtype")
        selected = bool(entry.get("selected", True))
        normalized.append({"source": source, "rename": rename, "dtype": dtype, "selected": selected})
    return normalized


def _validate_unique_output_names(select_fields: list[dict[str, Any]]) -> None:
    output_names = [field["rename"] for field in select_fields]
    if len(output_names) != len(set(output_names)):
        raise ValueError("Duplicate output field names are not supported in this slice")


def _convert_series(series: pd.Series, dtype: str | None) -> pd.Series:
    if dtype is None:
        return series.copy()
    if dtype not in SUPPORTED_TYPE_MAP:
        raise ValueError(f"Unsupported Select dtype conversion: {dtype}")
    return series.astype(SUPPORTED_TYPE_MAP[dtype])


def select_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _validate_inputs(inputs)
    select_fields = _normalize_select_fields(config)
    explicit_sources = {field["source"] for field in select_fields if field["source"] != "*Unknown"}
    selected_explicit_fields = [
        field
        for field in select_fields
        if field["selected"] and field["source"] != "*Unknown"
    ]
    ensure_fields_exist(input_frame, [field["source"] for field in selected_explicit_fields])

    output_columns: dict[str, pd.Series] = {}
    output_names: list[str] = []
    for field in select_fields:
        if not field["selected"]:
            continue
        if field["source"] == "*Unknown":
            for column in input_frame.columns:
                if column not in explicit_sources and column not in output_columns:
                    output_names.append(column)
                    output_columns[column] = input_frame[column].copy()
            continue
        output_names.append(field["rename"])
        output_columns[field["rename"]] = _convert_series(
            input_frame[field["source"]],
            field["dtype"],
        )
    output_fields = [{"source": name, "rename": name, "dtype": None} for name in output_names]
    _validate_unique_output_names(output_fields)

    output_frame = pd.DataFrame(output_columns, index=input_frame.index)
    outputs = {"Output": output_frame}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Select",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "select_fields": select_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output_frame),
        },
    )
    return outputs


class SelectTool(BaseTool):
    tool_type = "Select"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return select_tool(inputs, config, context)
