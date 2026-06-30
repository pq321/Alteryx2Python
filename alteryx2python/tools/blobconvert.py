from __future__ import annotations

import base64
import hashlib
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("BlobConvert tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _encoding(code_page: str) -> str:
    normalized = code_page.upper()
    if normalized == "UTF16":
        return "utf-16"
    if normalized in {"UTF8", "UTF-8", ""}:
        return "utf-8"
    return code_page


def _as_bytes(value: Any, text_code_page: str = "") -> bytes:
    if value is None or pd.isna(value):
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    return str(value).encode(_encoding(text_code_page))


def _blob_to_text(value: Any, mode: str, text_code_page: str) -> str:
    blob = _as_bytes(value)
    normalized = mode.upper()
    if normalized == "BASE64":
        return base64.b64encode(blob).decode("ascii")
    if normalized == "HEX":
        return blob.hex().upper()
    if normalized == "MD5":
        return hashlib.md5(blob).hexdigest()
    if normalized == "TEXT":
        return blob.decode(_encoding(text_code_page))
    if normalized == "REPORTSNIPPET":
        payload = base64.b64encode(blob).decode("ascii")
        return f'<img src="data:application/octet-stream;base64,{payload}" />'
    raise NotImplementedError(f"BlobConvert from-blob mode is not supported: {mode}")


def _text_to_blob(value: Any, mode: str, text_code_page: str) -> bytes:
    if value is None or pd.isna(value):
        return b""
    normalized = mode.upper()
    text_value = "" if value is None else str(value)
    if normalized == "BASE64":
        return base64.b64decode(text_value)
    if normalized == "HEX":
        return bytes.fromhex(text_value)
    if normalized == "TEXT":
        return text_value.encode(_encoding(text_code_page))
    raise NotImplementedError(f"BlobConvert to-blob mode is not supported: {mode}")


def blobconvert_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    field = str(config.get("field", ""))
    if not field:
        raise ValueError("BlobConvert config requires field")
    ensure_fields_exist(input_frame, [field])

    mode = str(config.get("mode", ""))
    text_code_page = str(config.get("text_code_page", ""))
    to_blob = bool(config.get("to_blob", False))
    output = input_frame.copy()
    if to_blob:
        output[field] = [_text_to_blob(value, mode, text_code_page) for value in output[field]]
    else:
        output[field] = [_blob_to_text(value, mode, text_code_page) for value in output[field]]

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="BlobConvert",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "field": field,
            "mode": mode,
            "to_blob": to_blob,
            "text_code_page": text_code_page,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class BlobConvertTool(BaseTool):
    tool_type = "BlobConvert"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return blobconvert_tool(inputs, config, context)
