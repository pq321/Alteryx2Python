from __future__ import annotations

from typing import Any
from pathlib import Path
import warnings
from zipfile import BadZipFile

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.csv_input import read_delimited_file
from alteryx2python.tools.dbfileinput import _delimiter, _encoding, _header_row, _import_line, _record_limit, read_excel_selection


def read_list_options(config):
    mode, action = config.get("mode"), config.get("read_list_type")
    if mode != "ReadList" or action != "Path":
        raise NotImplementedError(f"Dynamic Input requires ReadList / Path, got {mode!r} / {action!r}")
    template = config.get("input_configuration", {})
    reference = template.get("file", "")
    suffix = Path(reference.partition("|||")[0]).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise NotImplementedError(f"Dynamic Input template format is unsupported: {suffix or 'unspecified'}")
    attributes = template.get("file_attributes", {})
    if attributes.get("OutputFileName") not in {None, "", "None"}:
        raise NotImplementedError("Dynamic Input template uses an unsupported filename output field")
    field = config.get("read_list_field")
    if not field:
        raise ValueError("Dynamic Input requires a ReadList_Field")
    behaviour = (config.get("error_behaviour") or "Error").strip().lower()
    if behaviour not in {"error", "warning"}:
        raise NotImplementedError(f"Unsupported Dynamic Input ErrorBehaviour: {behaviour!r}")
    return field, reference, behaviour, {
        "header": 0 if _header_row(template) else None,
        "skiprows": max(_import_line(template) - 1, 0),
        "nrows": _record_limit(template),
        **({"delimiter": _delimiter(template), "encoding": _encoding(template)} if suffix == ".csv" else {}),
    }


def read_file_list(frame, field, template, read_options, input_dir, behaviour="error", on_warning=None):
    template_path, _, template_sheet = template.partition("|||")
    suffix = Path(template_path).suffix.lower()
    if field not in frame:
        raise KeyError(f"Dynamic Input path field is missing: {field!r}")
    frames = []
    def read_one(reference, options):
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError(f"Dynamic Input path in {field!r} must be nonempty text")
        filename, _, sheet = reference.partition("|||")
        path = Path(input_dir) / filename
        if path.suffix.lower() != suffix:
            raise ValueError(f"Dynamic Input expected {suffix} files, got {path.name!r}")
        if suffix == ".csv":
            if sheet or template_sheet:
                raise NotImplementedError("CSV Dynamic Input does not support sheet selectors")
            data = read_delimited_file(path, **options)
        else:
            data = read_excel_selection(path, sheet or template_sheet, allow_bare=True, **options)
        if options["header"] is None:
            data.columns = [f"F{index}" for index in range(1, len(data.columns) + 1)]
        return data

    paths = frame[field].tolist()
    valid_paths = {value for value in paths if isinstance(value, str) and value.strip()}
    has_invalid_path = any(not isinstance(value, str) or not value.strip() for value in paths)
    if has_invalid_path and behaviour != "warning":
        raise ValueError(f"Dynamic Input path in {field!r} must be nonempty text")
    references = sorted(valid_paths, key=lambda path: (path.casefold(), path))
    if has_invalid_path:
        references.append(None)
    try:
        expected_columns = list(read_one(template, {**read_options, "nrows": 0}).columns) if references else None
    except (OSError, ValueError, BadZipFile, NotImplementedError):
        # A portable workflow can still use a complete source path when its saved template is unavailable.
        expected_columns = None
    first_failure = None
    for reference in references:
        try:
            data = read_one(reference, read_options)
            if expected_columns is not None and list(data.columns) != expected_columns:
                raise ValueError("column names differ from the Dynamic Input schema")
        except (OSError, ValueError, BadZipFile) as error:
            if behaviour != "warning":
                raise
            message = f"Dynamic Input skipped {reference!r}: {error}"
            if first_failure is None:
                first_failure = (message, error)
            if on_warning is None:
                warnings.warn(message, RuntimeWarning, stacklevel=2)
            else:
                on_warning(message)
        else:
            if expected_columns is None:
                expected_columns = list(data.columns)
            frames.append(data)
    if frames:
        return pd.concat(frames, ignore_index=True)
    try:
        return read_one(template, read_options).iloc[:0]
    except (OSError, ValueError, BadZipFile, NotImplementedError):
        if first_failure is not None:
            message, error = first_failure
            raise ValueError(f"No Dynamic Input source could be read and the template schema is unavailable. {message}") from error
        raise


def dynamicinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    field, template, behaviour, options = read_list_options(config)
    input_frame = inputs.get("Input")
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    base = (context.runtime_config or {}).get("input_dir") or config.get("base_dir") or "."
    output = read_file_list(input_frame, field, template, options, base, behaviour, context.record_warning)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DynamicInput",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame} if isinstance(input_frame, pd.DataFrame) else {},
        outputs=outputs,
        status="success",
        config={
            "mode": config.get("mode", ""),
            "input_configuration": config.get("input_configuration", {}),
            "modifications": config.get("modifications", {}),
            "external_input_read_performed": True,
            "input_schema": snapshot_schema(input_frame) if isinstance(input_frame, pd.DataFrame) else {},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DynamicInputTool(BaseTool):
    tool_type = "DynamicInput"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return dynamicinput_tool(inputs, config, context)
