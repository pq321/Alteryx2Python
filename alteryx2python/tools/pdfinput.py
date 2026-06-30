from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _resolve_path(value: str, base_dir: str | None) -> str:
    if not value:
        return ""
    path = Path(value)
    if not path.is_absolute() and base_dir:
        path = Path(base_dir) / path
    return str(path)


def pdfinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = inputs.get("Input")
    if input_frame is not None and not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    output = input_frame.copy() if isinstance(input_frame, pd.DataFrame) else pd.DataFrame()
    pdf_directory = _resolve_path(str(config.get("pdf_directory", "")), config.get("base_dir"))
    if "PDFDirectory" not in output.columns:
        output["PDFDirectory"] = pdf_directory
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="PDFInput",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame} if isinstance(input_frame, pd.DataFrame) else {},
        outputs=outputs,
        status="success",
        config={
            "field": config.get("field", ""),
            "mode": config.get("mode", ""),
            "pdf_directory": pdf_directory,
            "pdf_read_performed": False,
            "input_schema": snapshot_schema(input_frame) if isinstance(input_frame, pd.DataFrame) else {},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class PDFInputTool(BaseTool):
    tool_type = "PDFInput"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return pdfinput_tool(inputs, config, context)
