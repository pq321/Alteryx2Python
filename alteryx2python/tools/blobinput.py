from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _resolve_path(path_text: str, base_dir: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path(base_dir, path_text).resolve()


def _read_blob(path: Path, stop_on_error: bool) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        if stop_on_error:
            raise
        return b""


def _chunks(blob: bytes, chunk_size: int) -> list[bytes]:
    if chunk_size <= 0:
        return [blob]
    return [blob[index : index + chunk_size] for index in range(0, len(blob), chunk_size)] or [b""]


def blobinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = inputs.get("Input")
    if input_frame is not None and not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    file_name = str(config.get("file_name", ""))
    filename_field = str(config.get("modify_filename_field", ""))
    stop_on_error = bool(config.get("stop_on_error", True))
    split_blobs = bool(config.get("split_blobs", False))
    chunk_size = int(config.get("blob_chunk_size") or 0)
    base_dir = str(config.get("base_dir", ""))
    source = input_frame if isinstance(input_frame, pd.DataFrame) else pd.DataFrame([{}])

    rows: list[dict[str, Any]] = []
    for _, row in source.iterrows():
        row_dict = row.to_dict()
        path_text = str(row_dict.get(filename_field) or file_name)
        path = _resolve_path(path_text, base_dir)
        blob = _read_blob(path, stop_on_error)
        for chunk_index, chunk in enumerate(_chunks(blob, chunk_size) if split_blobs else [blob], start=1):
            output_row = dict(row_dict)
            output_row["FileName"] = path_text
            output_row["FullPath"] = str(path)
            output_row["Blob"] = chunk
            if split_blobs:
                output_row["BlobChunkID"] = chunk_index
            rows.append(output_row)

    output = pd.DataFrame(rows)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="BlobInput",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame} if isinstance(input_frame, pd.DataFrame) else {},
        outputs=outputs,
        status="success",
        config={
            "file_name": file_name,
            "modify_filename_field": filename_field,
            "split_blobs": split_blobs,
            "input_schema": snapshot_schema(input_frame) if isinstance(input_frame, pd.DataFrame) else {},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class BlobInputTool(BaseTool):
    tool_type = "BlobInput"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return blobinput_tool(inputs, config, context)
