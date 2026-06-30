from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def textinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if inputs:
        raise ValueError("TextInput does not accept input anchors")

    fields = [str(field) for field in config.get("fields", [])]
    rows = config.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("TextInput config requires rows")
    if not fields:
        raise ValueError("TextInput config requires fields")

    normalized_rows = [_normalize_row(row, fields) for row in rows]
    output = pd.DataFrame(normalized_rows, columns=fields, dtype=object)

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="TextInput",
        source_tool_id=config.get("source_tool_id"),
        inputs={},
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "fields": fields,
            "num_rows": config.get("num_rows"),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


def _normalize_row(row: Any, fields: list[str]) -> list[str]:
    if not isinstance(row, list):
        raise ValueError("TextInput row entries must be lists")
    if len(row) != len(fields):
        raise ValueError(f"TextInput row has {len(row)} cells for {len(fields)} fields")
    return ["" if value is None else str(value) for value in row]


class TextInputTool(BaseTool):
    tool_type = "TextInput"
    input_anchors = ()
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return textinput_tool(inputs, config, context)
