from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


FORMAT_MAP = {
    "Month dd, yyyy": "%B %d, %Y",
    "day, dd Month, yyyy": "%A, %d %B, %Y",
    "day, Month dd, yyyy": "%A, %B %d, %Y",
    "MM-dd/yyyy": "%m-%d/%Y",
    "HH:mm:ss": "%H:%M:%S",
}


def _format_for(format_name: str) -> str:
    return FORMAT_MAP.get(format_name, format_name)


def datetime_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("DateTime tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    input_field = str(config.get("input_field_name", ""))
    output_field = str(config.get("output_field_name", input_field))
    format_name = str(config.get("format", ""))
    ensure_fields_exist(input_frame, [input_field])

    output = input_frame.copy()
    if config.get("is_from"):
        parsed = pd.to_datetime(output[input_field], errors="coerce")
        output[output_field] = parsed.dt.strftime(_format_for(format_name)).fillna("")
    else:
        parsed = pd.to_datetime(output[input_field], format=_format_for(format_name), errors="coerce")
        if format_name == "HH:mm:ss":
            output[output_field] = parsed.dt.strftime("%H:%M:%S").fillna("")
        else:
            output[output_field] = parsed.dt.strftime("%Y-%m-%d").fillna("")

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DateTime",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "input_field_name": input_field,
            "output_field_name": output_field,
            "format": format_name,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DateTimeTool(BaseTool):
    tool_type = "DateTime"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return datetime_tool(inputs, config, context)
