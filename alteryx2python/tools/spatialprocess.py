from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("SpatialProcess tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _process_value(field1_value: Any, field2_value: Any, action: str) -> Any:
    normalized = action.lower()
    if normalized in {"combine", "union"}:
        if pd.isna(field1_value) or field1_value == "":
            return field2_value
        if pd.isna(field2_value) or field2_value == "":
            return field1_value
        return f"GEOMETRYCOLLECTION ({field1_value}, {field2_value})"
    if normalized in {"createintersection", "intersection"}:
        return field1_value if str(field1_value) == str(field2_value) else field2_value
    return field2_value if "from2" in normalized else field1_value


def spatialprocess_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    field1 = str(config.get("field1", ""))
    field2 = str(config.get("field2", ""))
    ensure_fields_exist(input_frame, [field1, field2])

    action = str(config.get("action", ""))
    output_field = str(config.get("output_field", "") or "SpatialObj_Process")
    output = input_frame.copy()
    output[output_field] = [
        _process_value(row[field1], row[field2], action) for _, row in input_frame.iterrows()
    ]
    if bool(config.get("no_empty", False)):
        output = output[output[output_field].notna() & (output[output_field] != "")].reset_index(drop=True)

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="SpatialProcess",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "field1": field1,
            "field2": field2,
            "action": action,
            "no_empty": bool(config.get("no_empty", False)),
            "output_field": output_field,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class SpatialProcessTool(BaseTool):
    tool_type = "SpatialProcess"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return spatialprocess_tool(inputs, config, context)
