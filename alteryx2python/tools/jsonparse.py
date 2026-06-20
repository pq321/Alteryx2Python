from __future__ import annotations

import json
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _flatten_json(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        rows: list[tuple[str, Any]] = []
        for key, child in value.items():
            child_name = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_json(child, child_name))
        return rows
    if isinstance(value, list):
        rows = []
        for index, child in enumerate(value):
            child_name = f"{prefix}.{index}" if prefix else str(index)
            rows.extend(_flatten_json(child, child_name))
        return rows
    return [(prefix, value)]


def _stringify_json_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def jsonparse_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("JSONParse tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    json_field = str(config.get("json_field", ""))
    if not json_field:
        raise ValueError("JSONParse tool config requires json_field")
    ensure_fields_exist(input_frame, [json_field])

    include_in_output = bool(config.get("include_in_output", False))
    rows: list[dict[str, Any]] = []
    for source_row in input_frame.to_dict("records"):
        parsed = json.loads(source_row[json_field])
        for name, value in _flatten_json(parsed):
            output_row: dict[str, Any] = {}
            if include_in_output:
                output_row.update(source_row)
            else:
                output_row.update(
                    {
                        field: field_value
                        for field, field_value in source_row.items()
                        if field != json_field
                    }
                )
            output_row["JSON_Name"] = name
            output_row["JSON_ValueString"] = _stringify_json_value(value)
            rows.append(output_row)

    output = pd.DataFrame(rows)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="JSONParse",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "json_field": json_field,
            "include_in_output": include_in_output,
            "single_field": config.get("single_field"),
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class JSONParseTool(BaseTool):
    tool_type = "JSONParse"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return jsonparse_tool(inputs, config, context)
