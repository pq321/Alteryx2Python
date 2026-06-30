from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def sort_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Sort tool requires an Input anchor")
    input_frame = inputs["Input"]
    sort_fields = [field for field in config.get("sort_fields", []) if isinstance(field, dict)]
    if not sort_fields:
        raise ValueError("Sort tool config requires sort_fields")

    fields = [str(field.get("field", "")) for field in sort_fields]
    ensure_fields_exist(input_frame, fields)
    ascending = [_is_ascending(str(field.get("order", "Ascending"))) for field in sort_fields]
    output = input_frame.sort_values(by=fields, ascending=ascending, kind="mergesort").reset_index(drop=True)

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Sort",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "sort_fields": sort_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


def _is_ascending(order: str) -> bool:
    normalized = order.strip().lower()
    if normalized == "ascending":
        return True
    if normalized == "descending":
        return False
    raise ValueError(f"Unsupported Sort order: {order}")


class SortTool(BaseTool):
    tool_type = "Sort"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return sort_tool(inputs, config, context)
