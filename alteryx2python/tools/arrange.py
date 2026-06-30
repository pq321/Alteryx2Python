from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _required_source_fields(columns: list[dict[str, Any]], rows: list[list[str]]) -> list[str]:
    source_fields: list[str] = []
    for values in rows:
        for column, value in zip(columns, values, strict=False):
            if column.get("type") == "combobox" and value:
                source_fields.append(str(value))
    return source_fields


def arrange_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Arrange tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    key_fields = [str(field) for field in config.get("key_fields", [])]
    output_columns = [column for column in config.get("output_columns", []) if isinstance(column, dict)]
    output_rows = [row for row in config.get("output_rows", []) if isinstance(row, list)]
    ensure_fields_exist(input_frame, [*key_fields, *_required_source_fields(output_columns, output_rows)])

    rows: list[dict[str, Any]] = []
    for _, input_row in input_frame.iterrows():
        key_values = {field: input_row[field] for field in key_fields}
        for configured_values in output_rows:
            output_row = dict(key_values)
            for column, value in zip(output_columns, configured_values, strict=False):
                column_name = str(column.get("name", ""))
                if not column_name:
                    continue
                output_row[column_name] = input_row[value] if column.get("type") == "combobox" and value else value
            rows.append(output_row)

    output = pd.DataFrame(rows)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Arrange",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "key_fields": key_fields,
            "output_columns": output_columns,
            "output_rows": output_rows,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class ArrangeTool(BaseTool):
    tool_type = "Arrange"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return arrange_tool(inputs, config, context)
