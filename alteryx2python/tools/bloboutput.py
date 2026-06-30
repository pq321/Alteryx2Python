from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def bloboutput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("BlobOutput tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="BlobOutput",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs={},
        status="success",
        config={
            "file_name": config.get("file_name", ""),
            "modify_method": config.get("modify_method", ""),
            "modify_filename_field": config.get("modify_filename_field", ""),
            "blob_field": config.get("blob_field", ""),
            "external_write_performed": False,
            "input_schema": snapshot_schema(input_frame),
        },
    )
    return {}


class BlobOutputTool(BaseTool):
    tool_type = "BlobOutput"
    input_anchors = ("Input",)
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return bloboutput_tool(inputs, config, context)
