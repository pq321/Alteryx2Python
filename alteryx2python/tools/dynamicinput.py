from __future__ import annotations

from typing import Any
from pathlib import Path

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.dbfileinput import _clean_selector, _delimiter, _encoding, _header_row, _import_line, _record_limit


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
    return field, reference, {
        "header": 0 if _header_row(template) else None,
        "skiprows": max(_import_line(template) - 1, 0),
        "nrows": _record_limit(template),
        **({"delimiter": _delimiter(template), "encoding": _encoding(template)} if suffix == ".csv" else {}),
    }


def read_file_list(frame, field, template, read_options, input_dir):
    template_path, _, template_sheet = template.partition("|||")
    suffix = Path(template_path).suffix.lower()
    if field not in frame:
        raise KeyError(f"Dynamic Input path field is missing: {field!r}")
    frames = []
    paths = frame[field].tolist()
    if any(not isinstance(reference, str) or not reference.strip() for reference in paths):
        raise ValueError(f"Dynamic Input path in {field!r} must be nonempty text")
    for reference in sorted(set(paths), key=lambda path: (path.casefold(), path)) or [template]:
        filename, _, sheet = reference.partition("|||")
        path = Path(input_dir) / filename
        if path.suffix.lower() != suffix:
            raise ValueError(f"Dynamic Input expected {suffix} files, got {path.name!r}")
        if suffix == ".csv":
            if sheet or template_sheet:
                raise NotImplementedError("CSV Dynamic Input does not support sheet selectors")
            data = pd.read_csv(path, **read_options)
        else:
            selector = _clean_selector(sheet or template_sheet)
            if selector and not selector.endswith("$"):
                raise NotImplementedError("Excel Dynamic Input supports sheet selectors only")
            data = pd.read_excel(path, sheet_name=selector[:-1] if selector else 0, **read_options)
        if read_options["header"] is None:
            data.columns = [f"F{index}" for index in range(1, len(data.columns) + 1)]
        if frames and list(data.columns) != list(frames[0].columns):
            raise ValueError(f"Dynamic Input schema differs for {path.name!r}")
        frames.append(data)
    return pd.concat(frames, ignore_index=True) if paths else frames[0].iloc[:0]


def dynamicinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    field, template, options = read_list_options(config)
    input_frame = inputs.get("Input")
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    base = (context.runtime_config or {}).get("input_dir") or config.get("base_dir") or "."
    output = read_file_list(input_frame, field, template, options, base)
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
