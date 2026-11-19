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


def blob_input_options(config):
    method = str(config.get("modify_method") or "").strip().lower()
    if method not in {"", "none", "append", "prepend", "filename", "path"}:
        raise NotImplementedError(f"Unsupported Blob Input filename mode: {method}")
    native_output = bool(config.get("native_output"))
    split = bool(config.get("split_blobs"))
    chunk_size = int(config.get("blob_chunk_size") or (1024 if native_output else 0)) if split else 0
    if native_output and split and chunk_size <= 0:
        raise ValueError("Blob Input chunk size must be positive")
    return (
        str(config.get("file_name") or ""), str(config.get("modify_filename_field") or ""), method,
        bool(config.get("stop_on_error", True)), split, chunk_size * (1024 if native_output else 1),
        native_output,
    )


def _blob_path(file_name, value, method):
    if method in {"", "path"}:
        return value if value is not None else file_name if not method else ""
    path = Path(file_name)
    stem = {"append": path.stem + value, "prepend": value + path.stem, "filename": value}[method]
    return str(path.with_name(stem + path.suffix))


def read_blob_rows(frame, base_dir, file_name, field, method, stop_on_error, split, chunk_size, native_output):
    if frame is not None and not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    use_field = frame is not None and method != "none" and bool(method or field)
    if use_field and field not in frame.columns:
        raise KeyError(f"Blob Input requires filename field {field!r}")
    if not file_name and (not use_field or method not in {"", "path"}):
        raise ValueError("Blob Input requires a filename or a field replacing the entire path")
    source = pd.DataFrame(index=range(1)) if frame is None else frame
    paths = source[field].tolist() if use_field else [None] * len(source)
    chunk_field = "BlobNumber" if native_output else "BlobChunkID"
    indexes, names, full_paths, blobs, numbers = [], [], [], [], []
    for index, field_value in enumerate(paths):
        value = None if field_value is None or pd.isna(field_value) else str(field_value)
        path_text = _blob_path(file_name, value, method) if use_field and (value is not None or not method) else (
            "" if use_field else file_name
        )
        if not path_text and stop_on_error:
            raise ValueError(f"Blob Input observed an empty path in {field!r}")
        path = _resolve_path(path_text, base_dir) if path_text else None
        blob = _read_blob(path, stop_on_error) if path else b""
        for chunk_index, chunk in enumerate(_chunks(blob, chunk_size) if split else [blob], 1):
            indexes.append(index)
            blobs.append(chunk)
            if not native_output:
                names.append(path_text)
                full_paths.append(str(path) if path else "")
            if split:
                numbers.append(chunk_index)
    output = source.iloc[indexes].reset_index(drop=True)
    if not native_output:
        output["FileName"] = pd.Series(names, dtype=object)
        output["FullPath"] = pd.Series(full_paths, dtype=object)
    output["Blob"] = pd.Series(blobs, dtype=object)
    if split:
        output[chunk_field] = pd.Series(numbers, dtype="int32" if native_output else "int64")
    if native_output:
        declarations = {field["name"]: field for field in output.attrs.get("alteryx_schema") or []}
        declarations["Blob"] = {"name": "Blob", "type": "Blob", "size": None, "scale": None}
        if split:
            declarations[chunk_field] = {"name": chunk_field, "type": "Int32", "size": 4, "scale": None}
        output.attrs["alteryx_schema"] = [declarations[name] for name in output.columns if name in declarations]
    return output


def blobinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = inputs.get("Input")
    options = blob_input_options(config)
    base_dir = (context.runtime_config or {}).get("input_dir") or config.get("base_dir") or "."
    output = read_blob_rows(input_frame, base_dir, *options)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="BlobInput",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame} if isinstance(input_frame, pd.DataFrame) else {},
        outputs=outputs,
        status="success",
        config={
            "file_name": config.get("file_name", ""),
            "modify_filename_field": config.get("modify_filename_field", ""),
            "split_blobs": config.get("split_blobs", False),
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
