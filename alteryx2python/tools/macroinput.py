from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.textinput import textinput_tool


def macroinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    outputs = textinput_tool(inputs, config, context)
    output = outputs["Output"]
    context.traces.pop()
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="MacroInput",
        source_tool_id=config.get("source_tool_id"),
        inputs={},
        outputs=outputs,
        status="success",
        config={
            "source": config.get("source"),
            "fields": list(output.columns),
            "num_rows": len(output.index),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class MacroInputTool(BaseTool):
    tool_type = "MacroInput"
    input_anchors = ()
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return macroinput_tool(inputs, config, context)
