"""Bounded IO templates with configuration resolved during compilation."""
from __future__ import annotations

import math
from pathlib import PurePosixPath, PureWindowsPath

import pandas as pd

from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.tools.dbfileinput import (
    _clean_selector,
    _delimiter,
    _encoding,
    _file_attribute,
    _header_row,
    _import_line,
    _record_limit,
    _split_alteryx_file_reference,
)
from alteryx2python.tools.dbfileoutput import _date_columns, _format_cell, _format_option, _line_ending, _max_records, write_xlsx, xlsx_output_options
from alteryx2python.tools.textinput import _infer_types, _normalize_row


def _path(value: str) -> PurePosixPath | PureWindowsPath:
    windows = PureWindowsPath(value)
    return windows if windows.drive or "\\" in value else PurePosixPath(value)


def _portable_input(raw: str, base_dir: str | None) -> str:
    path = _path(raw)
    if path.is_absolute():
        try:
            if not base_dir:
                raise ValueError("missing base_dir")
            path = path.relative_to(_path(str(base_dir)))
        except ValueError as exc:
            raise UnsupportedLowering("External absolute input requires an explicit portable binding") from exc
    elif path.anchor:
        raise UnsupportedLowering("Drive-relative input requires an explicit portable binding")
    return path.as_posix()


def _cell_literal(value: object) -> str:
    if value is pd.NA:
        return "pd.NA"
    if value is pd.NaT:
        return "pd.NaT"
    if isinstance(value, pd.Timestamp):
        return f"pd.Timestamp({value.isoformat()!r})"
    if isinstance(value, float) and not math.isfinite(value):
        return f"float({str(value)!r})"
    return repr(value)


def _text_input(config: dict, compiler=None) -> list[str]:
    fields = [str(field) for field in config.get("fields", [])]
    rows = config.get("rows", [])
    if not fields or len(set(fields)) != len(fields):
        raise UnsupportedLowering("TextInput requires nonempty, unique fields")
    if not isinstance(rows, list):
        raise UnsupportedLowering("TextInput config requires rows to be a list")
    normalized = [_normalize_row(row, fields) for row in rows]
    if config.get('_cell_parameters'):
        infer = compiler.linker.function(_infer_types)
        cells = config['_cell_parameters']
        columns = []
        for index, field in enumerate(fields):
            values = [f'str({cells[str(row_index) + ":" + str(index)]})' if str(row_index) + ':' + str(index) in cells else repr(row[index]) for row_index, row in enumerate(normalized)]
            columns.append(f'{field!r}: [{", ".join(values)}]')
        return [f'return {infer}(pd.DataFrame({{{", ".join(columns)}}}, dtype=object))']
    frame = _infer_types(pd.DataFrame(normalized, columns=fields, dtype=object))
    lines = ["output = pd.DataFrame({"]
    for name in fields:
        values = ", ".join(_cell_literal(value) for value in frame[name].tolist())
        lines.append(f"    {name!r}: pd.Series([{values}], dtype={str(frame[name].dtype)!r}),")
    lines.append("})")
    if schema := frame.attrs.get("alteryx_schema"):
        lines.append(f'output.attrs["alteryx_schema"] = {schema!r}')
    return lines + ["return output"]


def _input(config: dict, raw: str, selector: str | None) -> list[str]:
    suffix = _path(raw).suffix.lower()
    file_format = _file_attribute(config, "FileFormat")
    if suffix == ".yxdb" or file_format == "19":
        raise UnsupportedLowering("YXDB input is not supported yet")
    csv = file_format == "0" or suffix == ".csv"
    if not csv and not (file_format == "25" or suffix in {".xlsx", ".xls"}):
        raise UnsupportedLowering(f"Unsupported DbFileInput FileFormat: {file_format or suffix}")
    header = _header_row(config)
    skiprows, limit = max(_import_line(config) - 1, 0), _record_limit(config)
    path = _portable_input(raw, config.get("base_dir"))
    lines = [f"path = input_dir / {path!r}"]
    if config.get('_file_parameter'):
        parameter = config['_file_parameter']
        if selector:
            raise UnsupportedLowering('File parameters with worksheet/range selectors require a binding template')
        lines = [f'path = Path({parameter})', f'if path.suffix.lower() != {suffix!r}:', '    raise ValueError("File input parameter changes configured format")', 'path = input_dir / path']
    options = f"skiprows={skiprows!r}, nrows={limit!r}, header={0 if header else None!r}"
    if csv:
        lines.append(
            f"output = pd.read_csv(path, delimiter={_delimiter(config)!r}, "
            f"{options}, encoding={_encoding(config)!r})"
        )
    else:
        selector = _clean_selector(selector)
        if selector == "<List of Sheet Names>":
            raise UnsupportedLowering("Excel sheet-name list input is not supported yet")
        if selector and not selector.endswith("$"):
            raise UnsupportedLowering("Named ranges are not supported by DbFileInput yet")
        sheet = selector[:-1] if selector else 0
        lines += [
            "try:",
            f"    output = pd.read_excel(path, sheet_name={sheet!r}, {options})",
            "except ImportError as exc:",
            '    raise NotImplementedError("Excel input requires pandas optional Excel engine support") from exc',
        ]
    if not header:
        lines.append('output.columns = [f"F{index}" for index in range(1, len(output.columns) + 1)]')
    return lines + ["return output"]


def _output(config: dict, raw: str, selector: str | None, frame: str, compiler) -> list[str]:
    path = _path(raw)
    file_format = _file_attribute(config, "FileFormat")
    if path.suffix.lower() == ".xlsx" and file_format != "0":
        if config.get('_file_parameter'):
            raise UnsupportedLowering("Parameterized Excel output needs a verified binding")
        sheet, header = xlsx_output_options(config, selector)
        function = compiler.linker.function(write_xlsx)
        limit = _max_records(config)
        output = f"{frame}.head({limit!r})" if limit is not None else frame
        return [f"{function}(output_dir / {path.name!r}, {output}, {sheet!r}, header={header!r})", "return None"]
    if not (file_format == "0" or path.suffix.lower() in {".csv", ".eml", ".txt"}):
        if file_format == "25" or path.suffix.lower() in {".xlsx", ".xls"}:
            raise UnsupportedLowering("Excel output is not supported by DbFileOutput yet")
        raise UnsupportedLowering(f"Unsupported DbFileOutput FileFormat: {file_format or path.suffix}")
    if not path.name:
        raise UnsupportedLowering("DbFileOutput requires a filename")
    header = _format_option(config, "HeaderRow", "True").lower() == "true"
    delimiter = _format_option(config, "Delimeter", ",") or ","
    ending = _line_ending(config)
    code_page = _format_option(config, "CodePage", "28591")
    encoding = {"65001": "utf-8", "1200": "utf-16", "28591": "latin-1"}.get(code_page, f"cp{code_page}")
    limit = _max_records(config)
    format_cell = compiler.linker.function(_format_cell)
    date_columns = compiler.linker.function(_date_columns)
    lines = [
        f"output = {frame}.head({limit!r})" if limit is not None else f"output = {frame}",
        f"path = output_dir / {path.name!r}",
        "path.parent.mkdir(parents=True, exist_ok=True)",
        f"date_columns = {date_columns}(output)",
    ]
    if config.get('_file_parameter'):
        parameter = config['_file_parameter']
        lines[1:2] = [f'if Path({parameter}).suffix.lower() != {path.suffix.lower()!r}:', '    raise ValueError("File output parameter changes configured format")', f'path = output_dir / Path({parameter}).name']
    write_csv = [
        "rendered = output.astype(object)",
        "for index, column in enumerate(rendered.columns):",
        f"    rendered.iloc[:, index] = [{format_cell}(value, column in date_columns) for value in rendered.iloc[:, index]]",
        f"rendered.to_csv(path, index=False, header={header!r}, sep={delimiter!r}, "
        f"lineterminator={ending!r}, encoding={encoding!r})",
    ]
    if not header:
        lines += [
            "if len(output.columns) == 1:",
            "    date_only = output.columns[0] in date_columns",
            f"    values = [{format_cell}(value, date_only) for value in output.iloc[:, 0]]",
            f'    path.write_text({ending!r}.join(values) + {ending!r}, encoding={encoding!r}, newline="")',
            "else:",
        ] + ["    " + line for line in write_csv]
    else:
        lines += write_csv
    return lines + ["return None"]


def lower_io(kind: str, config: dict, frame: str | None, compiler=None) -> list[str] | None:
    """Return standalone function-body statements, or None for another tool."""
    if kind not in {"TextInput", "DbFileInput", "DbFileOutput", "DynamicInput", "DateTimeNow"}:
        return None
    try:
        if kind == "DateTimeNow":
            from alteryx2python.tools.datetimenow import FORMAT_MAP, date_time_frame

            output_format = config.get("output_format", "yyyy-MM-dd")
            if output_format not in FORMAT_MAP:
                raise UnsupportedLowering(f"DateTimeNow output format is not supported: {output_format}")
            function = compiler.linker.function(date_time_frame)
            return [f"return {function}(as_of or {config.get('now')!r}, {output_format!r})"]
        if kind == "DynamicInput":
            from alteryx2python.tools.dynamicinput import read_file_list, read_list_options

            if frame is None:
                raise UnsupportedLowering("Dynamic Input requires an Input frame")
            field, template, options = read_list_options(config)
            function = compiler.linker.function(read_file_list)
            return [f"return {function}({frame}, {field!r}, {template!r}, {options!r}, input_dir)"]
        if kind == "DbFileOutput" and frame is None:
            raise UnsupportedLowering("DbFileOutput requires an Input frame")
        if kind != "DbFileOutput" and frame is not None:
            raise UnsupportedLowering(f"{kind} does not accept data input anchors")
        if kind == "TextInput":
            return _text_input(config, compiler)
        file_value = str(config.get("file", ""))
        if not file_value:
            raise UnsupportedLowering(f"{kind} config requires file")
        raw, selector = _split_alteryx_file_reference(file_value)
        return _input(config, raw, selector) if kind == "DbFileInput" else _output(config, raw, selector, frame, compiler)
    except (ValueError, TypeError, OverflowError, NotImplementedError) as exc:
        if isinstance(exc, UnsupportedLowering):
            raise
        raise UnsupportedLowering(f"Unsupported {kind} configuration: {exc}") from exc
