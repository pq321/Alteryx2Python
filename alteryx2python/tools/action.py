from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _input_records(inputs: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for anchor, frame in inputs.items():
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            records.append({"anchor": anchor})
            continue
        first = frame.iloc[0].to_dict()
        records.append(
            {
                "anchor": anchor,
                "value": first.get("value", first.get("active", first.get("matched"))),
                "active": first.get("active"),
                "branch": first.get("branch", ""),
                "tool_type": first.get("tool_type", ""),
            }
        )
    return records


def _is_active(records: list[dict[str, Any]]) -> bool:
    if not records:
        return True
    active_values = [record.get("active") for record in records if record.get("active") is not None]
    if active_values:
        return any(bool(value) for value in active_values)
    return True


def action_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    records = _input_records(inputs)
    output = pd.DataFrame(
        [
            {
                "action_name": str(config.get("name", "") or ""),
                "description": str(config.get("description", "") or ""),
                "active": _is_active(records),
                "inputs": records,
            }
        ]
    )
    outputs = {"Action": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Action",
        source_tool_id=config.get("source_tool_id"),
        inputs={key: value for key, value in inputs.items() if isinstance(value, pd.DataFrame)},
        outputs=outputs,
        status="success",
        config={
            "name": str(config.get("name", "") or ""),
            "description": str(config.get("description", "") or ""),
            "active": bool(output.loc[0, "active"]),
            "input_count": len(records),
        },
    )
    return outputs


class ActionTool(BaseTool):
    tool_type = "Action"
    input_anchors = ("Question", "Condition")
    output_anchors = ("Action",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return action_tool(inputs, config, context)
