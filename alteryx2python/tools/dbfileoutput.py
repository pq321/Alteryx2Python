from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _file_attribute(config: dict[str, Any], name: str, default: str = "") -> str:
    attrs = config.get("file_attributes")
    if not isinstance(attrs, dict):
        return default
    value = attrs.get(name, default)
    return str(value) if value is not None else default


def _format_option(config: dict[str, Any], name: str, default: str = "") -> str:
    options = config.get("format_specific_options")
    if not isinstance(options, dict):
        return default
    value = options.get(name)
    if isinstance(value, dict):
        return str(value.get("text", default))
    return default if value is None else str(value)


def _split_alteryx_file_reference(file_value: str) -> tuple[str, str | None]:
    if "|||" not in file_value:
        return file_value, None
    path, selector = file_value.split("|||", 1)
    return path, selector.strip()


def _resolve_path(path_value: str, base_dir: str | None) -> Path:
    path_value = _expand_alteryx_path_tokens(path_value)
    path = Path(path_value)
    if not path.is_absolute() and base_dir:
        path = Path(base_dir) / path
    return path.resolve()


def _expand_alteryx_path_tokens(path_value: str) -> str:
    lower = path_value.lower()
    if lower.startswith("%temp%"):
        suffix = path_value[len("%temp%") :].lstrip("\\/")
        return str(Path(os.environ.get("TEMP", ".")) / suffix)
    return path_value


def _max_records(config: dict[str, Any]) -> int | None:
    raw = _file_attribute(config, "MaxRecords")
    if not raw:
        return None
    return int(raw)


def _line_ending(config: dict[str, Any]) -> str:
    style = _format_option(config, "LineEndStyle", "CRLF").upper()
    if style == "LF":
        return "\n"
    return "\r\n"


def _format_cell(value: Any) -> str:
    """Format a value the way the native CSV writer renders it.

    Alteryx writes integral doubles without a trailing ".0" (3.0 -> "3") and
    renders nulls as empty cells.
    """
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return str(value)


def _write_delimited_text(path: Path, output_frame: pd.DataFrame, config: dict[str, Any]) -> None:
    header = _format_option(config, "HeaderRow", "True").lower() == "true"
    delimiter = _format_option(config, "Delimeter", ",") or ","
    line_ending = _line_ending(config)
    code_page = _format_option(config, "CodePage", "28591")
    encoding = {"65001": "utf-8", "1200": "utf-16", "28591": "latin-1"}.get(code_page, f"cp{code_page}")

    path.parent.mkdir(parents=True, exist_ok=True)
    if not header and len(output_frame.columns) == 1:
        values = output_frame.iloc[:, 0].map(_format_cell).tolist()
        path.write_text(line_ending.join(values) + line_ending, encoding=encoding, newline="")
        return

    rendered = output_frame.copy()
    for column in rendered.columns:
        rendered[column] = rendered[column].map(_format_cell)
    rendered.to_csv(path, index=False, header=header, sep=delimiter, lineterminator=line_ending, encoding=encoding)


def dbfileoutput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("DbFileOutput tool requires an Input anchor")
    input_frame = inputs["Input"]
    file_value = str(config.get("file", ""))
    if not file_value:
        raise ValueError("DbFileOutput config requires file")

    raw_path, selector = _split_alteryx_file_reference(file_value)
    path = _resolve_path(raw_path, config.get("base_dir"))
    file_format = _file_attribute(config, "FileFormat")
    max_records = _max_records(config)
    output_frame = input_frame.head(max_records) if max_records is not None else input_frame

    if file_format == "0" or path.suffix.lower() in {".csv", ".eml", ".txt"}:
        _write_delimited_text(path, output_frame, config)
    elif file_format == "25" or path.suffix.lower() in {".xlsx", ".xls"}:
        raise NotImplementedError("Excel output is not supported by DbFileOutput yet")
    else:
        raise NotImplementedError(f"Unsupported DbFileOutput FileFormat: {file_format or path.suffix}")

    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DbFileOutput",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs={},
        status="success",
        config={
            "file": file_value,
            "resolved_path": str(path),
            "selector": selector,
            "file_format": file_format,
            "input_schema": snapshot_schema(output_frame),
        },
    )
    return {}


class DbFileOutputTool(BaseTool):
    tool_type = "DbFileOutput"
    input_anchors = ("Input",)
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return dbfileoutput_tool(inputs, config, context)
