from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def transpose_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Transpose tool requires an Input anchor")
    input_frame = inputs["Input"]
    key_fields = list(config.get("key_fields", []))
    data_fields = [
        field["field"]
        for field in config.get("data_fields", [])
        if isinstance(field, dict) and field.get("selected", False)
    ]
    ensure_fields_exist(input_frame, key_fields)
    missing_data_fields = [field for field in data_fields if field not in input_frame.columns]
    if missing_data_fields and str(config.get("error_warn", "")).lower() != "warn":
        ensure_fields_exist(input_frame, missing_data_fields)
    data_fields = [field for field in data_fields if field in input_frame.columns]

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
