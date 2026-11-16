from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.csv_input import read_delimited_file


def _node_text(node: Any, default: str = "") -> str:
    if isinstance(node, dict):
        if "text" in node:
            return str(node["text"])
        attrs = node.get("attributes")
        if isinstance(attrs, dict) and "value" in attrs:
            return str(attrs["value"])
    if node is None:
        return default
    return str(node)


def _option(config: dict[str, Any], name: str, default: str = "") -> str:
    options = config.get("format_specific_options")
    if not isinstance(options, dict):
        return default
    return _node_text(options.get(name), default)


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


def _clean_selector(selector: str | None) -> str | None:
    if selector is None:
        return None
    stripped = selector.strip()
    if len(stripped) >= 2 and (stripped[0], stripped[-1]) in {('`', '`'), ("'", "'"), ('"', '"'), ('[', ']')}:
        return stripped[1:-1]
    return stripped


def _resolve_path(path_value: str, base_dir: str | None) -> Path:
    path = Path(path_value)
    if not path.is_absolute() and path.exists():
        return path.resolve()
    if not path.is_absolute() and base_dir:
        path = Path(base_dir) / path
    return path.resolve()


def _record_limit(config: dict[str, Any]) -> int | None:
    raw = _file_attribute(config, "RecordLimit")
    if not raw:
        return None
    return int(raw)


def _import_line(config: dict[str, Any]) -> int:
    raw = _option(config, "ImportLine", "1")
    return int(raw or "1")


def _header_row(config: dict[str, Any]) -> bool:
    options = config.get("format_specific_options")
    if isinstance(options, dict) and "HeaderRow" in options:
        return str(_node_text(options.get("HeaderRow"), "True")).lower() == "true"
    raw = _option(config, "FirstRowData", "False")
    return str(raw).lower() == "false"


def _delimiter(config: dict[str, Any]) -> str:
    return _option(config, "Delimeter", ",") or ","


def _encoding(config: dict[str, Any]) -> str | None:
    code_page = _option(config, "CodePage", "").strip().lower()
    if code_page in {"", "0", "auto", "automatic"}:
        return None
    return {"28591": "iso-8859-1", "65001": "utf-8-sig", "1200": "utf-16",
            "1201": "utf-16-be", "shift-jis": "cp932", "shift_jis": "cp932"}.get(
                code_page, f"cp{code_page}" if code_page.isdecimal() else code_page)


def _read_csv(path: Path, config: dict[str, Any]) -> pd.DataFrame:
    if not _header_row(config):
        frame = read_delimited_file(
            path,
            delimiter=_delimiter(config),
            skiprows=max(_import_line(config) - 1, 0),
            nrows=_record_limit(config),
            encoding=_encoding(config),
            header=None,
        )
        frame.columns = [f"F{index}" for index in range(1, len(frame.columns) + 1)]
        return frame
    return read_delimited_file(
        path,
        delimiter=_delimiter(config),
        skiprows=max(_import_line(config) - 1, 0),
        nrows=_record_limit(config),
        encoding=_encoding(config),
    )


def excel_selection_options(selector, options, *, allow_bare=False):
    selector = _clean_selector(selector) or ""
    if selector == "<List of Sheet Names>":
        raise NotImplementedError("Excel sheet-name list input is not supported yet")
    bounds = re.fullmatch(r"(.+?)\$\$?([A-Za-z]+)\$?([1-9]\d*):\$?([A-Za-z]+)\$?([1-9]\d*)", selector)
    if bounds is None:
        if selector and not selector.endswith("$") and not allow_bare:
            raise NotImplementedError("Named ranges are not supported by DbFileInput yet")
        name = selector.removesuffix("$")
        if not name and selector:
            raise ValueError(f"Excel selector requires a worksheet name: {selector!r}")
        return {**options, "sheet_name": name or 0}

    sheet, start_col, start, end_col, end = bounds.groups()
    from openpyxl.utils.cell import column_index_from_string

    if int(start) > int(end) or column_index_from_string(start_col) > column_index_from_string(end_col):
        raise ValueError(f"Excel selector has a reversed cell range: {selector!r}")
    offset = options.get("skiprows", 0)
    rows = max(0, int(end) - int(start) + 1 - offset - int(options.get("header") is not None))
    limit = options.get("nrows")
    return {**options, "sheet_name": _clean_selector(sheet), "usecols": f"{start_col.upper()}:{end_col.upper()}",
            "skiprows": int(start) - 1 + offset, "nrows": rows if limit is None else min(rows, limit)}


def read_excel_selection(path, selector, *, allow_bare=False, **options):
    try:
        return pd.read_excel(path, **excel_selection_options(selector, options, allow_bare=allow_bare))
    except ImportError as exc:
        raise NotImplementedError("Excel input requires pandas optional Excel engine support") from exc


def _read_excel(path: Path, selector: str | None, config: dict[str, Any]) -> pd.DataFrame:
    header = _header_row(config)
    frame = read_excel_selection(path, selector, skiprows=max(_import_line(config) - 1, 0),
                                 nrows=_record_limit(config), header=0 if header else None)
    if not header:
        frame.columns = [f"F{index}" for index in range(1, len(frame.columns) + 1)]
    return frame


def dbfileinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if inputs:
        raise ValueError("DbFileInput does not accept input anchors")
    file_value = str(config.get("file", ""))
    if not file_value:
        raise ValueError("DbFileInput config requires file")

    raw_path, selector = _split_alteryx_file_reference(file_value)
    input_dir = (context.runtime_config or {}).get("input_dir")
    path = (Path(input_dir) / raw_path).resolve() if input_dir else _resolve_path(raw_path, config.get("base_dir"))
    file_format = _file_attribute(config, "FileFormat")

    if path.suffix.lower() == ".yxdb" or file_format == "19":
        from alteryx2python.yxdb_file import read_yxdb_records

        if selector:
            raise NotImplementedError("YXDB input does not support a sheet or range selector")
        schema, rows = read_yxdb_records(path, limit=_record_limit(config))
        output = pd.DataFrame(rows, columns=[field["name"] for field in schema], dtype=object)
        output.attrs["alteryx_schema"] = schema
    elif file_format == "0" or path.suffix.lower() == ".csv":
        output = _read_csv(path, config)
    elif file_format == "25" or path.suffix.lower() in {".xlsx", ".xls"}:
        output = _read_excel(path, selector, config)
    else:
        raise NotImplementedError(f"Unsupported DbFileInput FileFormat: {file_format or path.suffix}")

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DbFileInput",
        source_tool_id=config.get("source_tool_id"),
        inputs={},
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "file": file_value,
            "resolved_path": str(path),
            "file_format": file_format,
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DbFileInputTool(BaseTool):
    tool_type = "DbFileInput"
    input_anchors = ()
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return dbfileinput_tool(inputs, config, context)
