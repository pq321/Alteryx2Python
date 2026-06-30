from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _selected_fields(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    configured = [str(field) for field in config.get("fields", [])]
    explicit = [field for field in configured if field != "*Unknown" and field in frame.columns]
    if "*Unknown" in configured:
        explicit.extend(column for column in frame.columns if column not in explicit)
    return explicit or list(frame.columns)


def _auto_convert(series: pd.Series) -> pd.Series:
    if not pd.api.types.is_object_dtype(series) and not pd.api.types.is_string_dtype(series):
        return series
    non_empty = series.dropna().astype(str)
    non_empty = non_empty[non_empty != ""]
    if non_empty.empty:
        return series
    numeric = pd.to_numeric(non_empty, errors="coerce")
    if numeric.notna().all():
        converted = pd.to_numeric(series.replace("", pd.NA), errors="coerce")
        if (converted.dropna() % 1 == 0).all():
            return converted.astype("Int64")
        return converted
    return series


def autofield_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("AutoField tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    output = input_frame.copy()
    converted_fields = []
    for field in _selected_fields(output, config):
        before = str(output[field].dtype)
        output[field] = _auto_convert(output[field])
        after = str(output[field].dtype)
        if before != after:
            converted_fields.append({"field": field, "from": before, "to": after})

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="AutoField",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "converted_fields": converted_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class AutoFieldTool(BaseTool):
    tool_type = "AutoField"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return autofield_tool(inputs, config, context)
