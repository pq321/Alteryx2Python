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


def date_time_frame(now, output_format):
    if now is None:
        now = datetime.now()
    elif isinstance(now, str):
        now = datetime.fromisoformat(now)
    if not isinstance(now, datetime):
        raise TypeError("DateTimeNow config 'now' must be a datetime or ISO datetime string")

    strftime_format = FORMAT_MAP.get(output_format)
    if strftime_format is None:
        raise NotImplementedError(f"DateTimeNow output format is not supported: {output_format}")

    return pd.DataFrame({"DateTimeNow": [now.strftime(strftime_format)]})


def datetimenow_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    output_format = str(config.get("output_format", "yyyy-MM-dd"))
    now = (context.runtime_config or {}).get("as_of") or config.get("now")
    output = date_time_frame(now, output_format)
    declared_anchors = config.get("node_output_anchors", ())
    outputs = {"DTN" if "DTN" in declared_anchors or config.get("macro_path") else "Output": output}
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
