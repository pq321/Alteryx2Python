from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
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

    blob_field = config.get("blob_field")
    file_name = config.get("file_name")
    method = str(config.get("modify_method", "")).lower()
    field = config.get("modify_filename_field")
    if not blob_field or (not file_name and method != "path"):
        raise ValueError("Blob Output requires a blob field and a destination")
    if method not in {"", "none", "filename", "path"}:
        raise NotImplementedError(f"Unsupported Blob Output filename mode: {method}")
    if method in {"filename", "path"} and not field:
        raise ValueError("Blob Output filename mode requires a configured field")
    ensure_fields_exist(input_frame, [blob_field] + ([field] if method in {"filename", "path"} else []))

    base_dir = Path(config.get("base_dir", "."))
    destination = Path(file_name or "")
    writes = []
    for row in input_frame.to_dict("records"):
        value = row[blob_field]
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError(f"Blob Output field {blob_field!r} must contain binary data")
        target = destination
        if method in {"filename", "path"}:
            name = row[field]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Blob Output requires a nonempty filename value")
            target = Path(name) if method == "path" else destination.with_name(name)
        writes.append((base_dir / target, value))
    for target, value in writes:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)

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
            "external_write_performed": bool(writes),
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
