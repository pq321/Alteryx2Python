from __future__ import annotations

from pathlib import Path
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


def _resolve_path(value: str, base_dir: str | None) -> str:
    if not value:
        return ""
    path = Path(value)
    if not path.is_absolute() and base_dir:
        path = Path(base_dir) / path
    return str(path)


def pdftotext_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    anchor, input_frame = _first_input(inputs)
    if isinstance(input_frame, pd.DataFrame):
        output = input_frame.copy()
    else:
        path_value = _resolve_path(str(config.get("path_input_value", "")), config.get("base_dir"))
        output = pd.DataFrame(
            [
                {
                    "File": Path(path_value).name if path_value else "",
                    "Path": path_value,
                    "Output Option": "metadata_only",
                    "Page": pd.NA,
                    "Row": pd.NA,
                    "Text": "",
                }
            ]
        )
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="PDFToText",
        source_tool_id=config.get("source_tool_id"),
        inputs={anchor: input_frame} if anchor and isinstance(input_frame, pd.DataFrame) else {},
        outputs=outputs,
        status="success",
        config={
            "language": config.get("language", ""),
            "extraction_mode": config.get("extraction_mode", ""),
            "path_input_mode": config.get("path_input_mode", ""),
            "path_input_value": config.get("path_input_value", ""),
            "pdf_text_extraction_performed": False,
            "input_schema": snapshot_schema(input_frame) if isinstance(input_frame, pd.DataFrame) else {},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class PDFToTextTool(BaseTool):
    tool_type = "PDFToText"
    input_anchors = ("Data Input", "Template Input")
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return pdftotext_tool(inputs, config, context)
