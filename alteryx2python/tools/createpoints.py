from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("CreatePoints tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _wkt_point(x_value: Any, y_value: Any) -> str | None:
    x = pd.to_numeric(pd.Series([x_value]), errors="coerce").iloc[0]
    y = pd.to_numeric(pd.Series([y_value]), errors="coerce").iloc[0]
    if pd.isna(x) or pd.isna(y):
        return None
    return f"POINT ({x:g} {y:g})"


def createpoints_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    x_field = str(config.get("x_field", ""))
    y_field = str(config.get("y_field", ""))
    mode = str(config.get("mode", ""))
    output_field = str(config.get("output_field", "Centroid") or "Centroid")
    if mode and mode != "Double":
        raise NotImplementedError(f"CreatePoints mode is not supported: {mode}")
    ensure_fields_exist(input_frame, [x_field, y_field])

    output = input_frame.copy()
    output[output_field] = [
        _wkt_point(x_value, y_value)
        for x_value, y_value in zip(output[x_field], output[y_field], strict=False)
    ]
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="CreatePoints",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "x_field": x_field,
            "y_field": y_field,
            "mode": mode,
            "output_field": output_field,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class CreatePointsTool(BaseTool):
    tool_type = "CreatePoints"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return createpoints_tool(inputs, config, context)
