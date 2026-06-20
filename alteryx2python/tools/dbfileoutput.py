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

    if file_format == "0" or path.suffix.lower() == ".csv":
        path.parent.mkdir(parents=True, exist_ok=True)
        output_frame.to_csv(path, index=False)
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
