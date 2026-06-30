from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _first_input(inputs: dict[str, pd.DataFrame]) -> tuple[str, pd.DataFrame] | tuple[None, None]:
    for anchor, frame in inputs.items():
        if isinstance(frame, pd.DataFrame):
            return anchor, frame
    return None, None


def jupytercode_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    anchor, input_frame = _first_input(inputs)
    output = input_frame.copy() if isinstance(input_frame, pd.DataFrame) else pd.DataFrame()
    outputs = {"Output": output}
    script = str(config.get("production_mode_script", ""))
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="JupyterCode",
        source_tool_id=config.get("source_tool_id"),
        inputs={anchor: input_frame} if anchor and isinstance(input_frame, pd.DataFrame) else {},
        outputs=outputs,
        status="success",
        config={
            "external_code_executed": False,
            "venv_name": config.get("venv_name", ""),
            "script_length": len(script),
            "input_schema": snapshot_schema(input_frame) if isinstance(input_frame, pd.DataFrame) else {},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class JupyterCodeTool(BaseTool):
    tool_type = "JupyterCode"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return jupytercode_tool(inputs, config, context)
