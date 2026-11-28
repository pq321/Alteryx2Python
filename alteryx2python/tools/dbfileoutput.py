from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
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
        return str(value.get("text", (value.get("attributes") or {}).get("value", default)))
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


def delivery_output_path(workflow_path, output_dir, input_dir, use_workflow_output_paths=False):
    if use_workflow_output_paths:
        return _resolve_path(str(workflow_path), input_dir)
    return Path(output_dir) / PureWindowsPath(workflow_path).name


def ensure_output_directory(directory):
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except PermissionError as error:
        raise PermissionError(f"Current account cannot create output directory: {directory}") from error


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


def _format_cell(value: Any, date_only: bool = False) -> str | None:
    """Format a value the way the native CSV writer renders it.

    Alteryx writes integral doubles without a trailing ".0" (3.0 -> "3") and
    renders nulls as empty cells.
    """
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if date_only and isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, float) and value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return str(value)


def _date_columns(frame: pd.DataFrame) -> set[str]:
    return {
        field["name"] for field in frame.attrs.get("alteryx_schema") or []
        if field.get("type") == "Date"
    }


def delimited_output_options(config):
    header = _format_option(config, "HeaderRow", "True").lower() == "true"
    delimiter = _format_option(config, "Delimeter", ",") or ","
    line_ending = _line_ending(config)
    code_page = _format_option(config, "CodePage", "28591")
    encoding = {"65001": "utf-8-sig" if _format_option(config, "WriteBOM", "False").lower() == "true" else "utf-8", "1200": "utf-16", "28591": "latin-1"}.get(code_page, f"cp{code_page}")
    return header, delimiter, line_ending, encoding


def write_delimited_table(path, frame, *, header, delimiter, line_ending, encoding, midnight_as_date=False):
    date_columns = _date_columns(frame)
    ensure_output_directory(path.parent)

    def format_value(value, column):
        date_only = column in date_columns
        if midnight_as_date and isinstance(value, pd.Timestamp) and value == value.normalize():
            date_only = True
        return _format_cell(value, date_only)

    def csv_field(value):
        if value is None:
            return ""
        if value == "" or delimiter in value or any(mark in value for mark in '"\r\n'):
            return '"' + value.replace('"', '""') + '"'
        return value

    with path.open("w", encoding=encoding, newline="") as stream:
        if header:
            stream.write(delimiter.join(csv_field(str(column)) for column in frame.columns) + line_ending)
        if not header and len(frame.columns) == 1:
            values = (format_value(value, frame.columns[0]) or "" for value in frame.iloc[:, 0])
            stream.write(line_ending.join(values) + line_ending)
            return
        for row in frame.itertuples(index=False, name=None):
            fields = (csv_field(format_value(value, column)) for column, value in zip(frame.columns, row))
            stream.write(delimiter.join(fields) + line_ending)


def write_delimited_frame(path, output_frame, header, delimiter, line_ending, encoding):
    write_delimited_table(path, output_frame, header=header, delimiter=delimiter, line_ending=line_ending, encoding=encoding)


def _write_delimited_text(path: Path, output_frame: pd.DataFrame, config: dict[str, Any]) -> None:
    write_delimited_frame(path, output_frame, *delimited_output_options(config))


def write_xlsx(path, frame, sheet="Sheet1", *, header=True, replace_sheet=False, sheet_index=None):
    ensure_output_directory(path.parent)
    frame = frame.map(lambda value: value.replace("\r\n", "\n") if isinstance(value, str) else value)
    if replace_sheet and path.is_file():
        with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as workbook:
            frame.to_excel(workbook, sheet_name=sheet, index=False, header=header)
            if sheet_index is not None:
                book = workbook.book
                current_index = book.sheetnames.index(sheet)
                book.move_sheet(sheet, offset=min(sheet_index, len(book.sheetnames) - 1) - current_index)
    else:
        frame.to_excel(path, sheet_name=sheet, index=False, header=header, engine="openpyxl")


def xlsx_output_options(config, selector):
    sheet = (selector or "Sheet1").strip("'`").removesuffix("$")
    if not sheet or any(character in sheet for character in ":\\/?*[]") or len(sheet) > 31:
        raise NotImplementedError("Excel output requires a single worksheet name")
    options = config.get("format_specific_options") or {}
    mode = _format_option(config, "OutputOption", "")
    if mode not in {"", "RemoveFile", "OverwriteFile", "Overwrite", "Create"}:
        raise NotImplementedError(f"Excel output mode is unsupported: {mode!r}. Use Overwrite File (Remove)")
    defaults = {
        "PreserveFormat": {"", "false", "0"},
        "UNCLocal": {"", "false", "0"},
        "SuppressBlankFile": {"", "false", "0"},
        "MipSensitivity": {""},
        "MipTenantId": {""},
    }
    unsupported = [
        option for option in options.keys() - {"OutputOption", "HeaderRow", "SkipFieldNames"}
        if _format_option(config, option).strip().lower() not in defaults.get(option, ())
    ]
    if unsupported:
        raise NotImplementedError("Unsupported Excel output options: " + ", ".join(sorted(unsupported)))
    header = _format_option(config, "HeaderRow", "True").lower() == "true"
    skip = _format_option(config, "SkipFieldNames", "False").strip().lower()
    if skip not in {"", "false", "0", "true", "1"}:
        raise ValueError(f"Invalid Excel SkipFieldNames setting: {skip!r}")
    return sheet, header and skip not in {"true", "1"}


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
    runtime = context.runtime_config or {}
    base = runtime.get('input_dir') if runtime.get('use_workflow_output_paths') else None
    path = _resolve_path(raw_path, base or config.get("base_dir"))
    file_format = _file_attribute(config, "FileFormat")
    max_records = _max_records(config)
    output_frame = input_frame.head(max_records) if max_records is not None else input_frame
    if file_format == "0" or path.suffix.lower() in {".csv", ".eml", ".txt"}:
        _write_delimited_text(path, output_frame, config)
    elif path.suffix.lower() == ".xlsx":
        sheet, header = xlsx_output_options(config, selector)
        write_xlsx(path, output_frame, sheet, header=header,
                   replace_sheet=_format_option(config, "OutputOption", "") in {"Overwrite", "Create"})
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
