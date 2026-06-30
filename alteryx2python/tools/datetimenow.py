from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


FORMAT_MAP = {
    "yyyy-MM-dd": "%Y-%m-%d",
    "yyyy-MM-dd HH:mm:ss": "%Y-%m-%d %H:%M:%S",
    "MM/dd/yyyy": "%m/%d/%Y",
}


def datetimenow_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    now = config.get("now")
    if now is None:
        now = datetime.now()
    elif isinstance(now, str):
        now = datetime.fromisoformat(now)
    if not isinstance(now, datetime):
        raise TypeError("DateTimeNow config 'now' must be a datetime or ISO datetime string")

    output_format = str(config.get("output_format", "yyyy-MM-dd"))
    strftime_format = FORMAT_MAP.get(output_format)
    if strftime_format is None:
        raise NotImplementedError(f"DateTimeNow output format is not supported: {output_format}")

    output = pd.DataFrame({"DateTimeNow": [now.strftime(strftime_format)]})
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DateTimeNow",
        source_tool_id=config.get("source_tool_id"),
        inputs=inputs,
        outputs=outputs,
        status="success",
        config={
            "output_format": output_format,
            "language": config.get("language", "English"),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DateTimeNowTool(BaseTool):
    tool_type = "DateTimeNow"
    input_anchors = ()
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return datetimenow_tool(inputs, config, context)
