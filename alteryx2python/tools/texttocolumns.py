from __future__ import annotations

import re
import warnings
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


BOOKEND_FLAGS = {1: ('"', '"'), 2: ("(", ")"), 8: ("'", "'"), 32: ("[", "]")}
SKIP_EMPTY = 16
KNOWN_SPLIT_FLAGS = sum(BOOKEND_FLAGS) | SKIP_EMPTY


def imported_split_options(config):
    field = str(config.get("field", ""))
    count = int(config.get("num_fields", 1))
    flags = int(config.get("flags", 0))
    mode = str(config.get("error_handling", "Last")).lower()
    if count < 1:
        raise ValueError("Text To Columns requires a positive column count")
    if mode not in {"last", "warn", "ignore", "error"}:
        raise NotImplementedError(f"Unsupported Text To Columns overflow policy: {mode}")
    if flags & ~KNOWN_SPLIT_FLAGS:
        raise NotImplementedError(f"Unsupported Text To Columns flags: {flags}")
    delimiters = str(config.get("delimiters", ""))
    delimiters = delimiters.replace(r"\s", " ").replace(r"\t", "\t").replace(r"\n", "\n").replace(r"\r", "\r")
    return field, str(config.get("root_name", field)), count, flags, mode, delimiters, bool(config["split_to_rows"])


def _partition_native(value, delimiters, flags):
    if pd.isna(value):
        return [(None, 0)]
    text = str(value)
    bookends = {opening: closing for bit, (opening, closing) in BOOKEND_FLAGS.items() if flags & bit}
    closing = []
    parts = []
    start = 0
    for end, char in enumerate(text):
        if closing and char == closing[-1]:
            closing.pop()
        elif char in bookends and (not closing or closing[-1] not in ("'", '"')):
            closing.append(bookends[char])
        elif not closing and char in delimiters:
            if end > start or not flags & SKIP_EMPTY:
                parts.append((text[start:end], end))
            start = end + 1
    if start < len(text) or (not text and not flags & SKIP_EMPTY):
        parts.append((text[start:], len(text)))
    return parts


def split_imported_field(frame, field, root, count, flags, mode, delimiters, split_to_rows, warn=None):
    records = frame[field].tolist()
    splits = [_partition_native(value, delimiters, flags) for value in records]
    if split_to_rows:
        indexes = [index for index, parts in enumerate(splits) for _ in parts]
        output = frame.iloc[indexes].reset_index(drop=True).copy()
        output[field] = pd.Series([part for parts in splits for part, _ in parts], dtype=object)
        return output
    names = [f"{root}{index}" for index in range(1, count + 1)]
    excess = False
    rows = []
    for value, parts in zip(records, splits):
        excess |= len(parts) > count
        cells = [part for part, _ in parts[:count]]
        if mode == "last" and count > 1 and len(parts) >= count:
            cells[-1] = str(value)[parts[count - 2][1] + 1:]
        rows.append(cells + [None] * (count - len(cells)))
    if excess:
        message = f"Text To Columns found excess delimiters in {field!r}"
        if mode == "error":
            raise ValueError(message)
        if mode == "warn":
            if warn is None:
                warnings.warn(message, RuntimeWarning, stacklevel=2)
            else:
                warn(message)
    output = frame.copy()
    for index, name in enumerate(names):
        output[name] = pd.Series([row[index] for row in rows], index=output.index, dtype=object)
    return output


def _delimiter_pattern(delimiters: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(delimiters):
        if delimiters[index:index + 2] == r"\s":
            parts.append(r"\s")
            index += 2
        else:
            parts.append(re.escape(delimiters[index]))
            index += 1
    return f"[{''.join(parts)}]+"


def _split_value(value: Any, delimiters: str) -> list[str]:
    text = "" if pd.isna(value) else str(value)
    if delimiters == "":
        return [text]
    return re.split(_delimiter_pattern(delimiters), text)


def _column_names(root_name: str, count: int) -> list[str]:
    return [f"{root_name}{index}" for index in range(1, count + 1)]


def _split_to_columns(input_frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    field = str(config.get("field", ""))
    root_name = str(config.get("root_name", field))
    num_fields = int(config.get("num_fields", 1))
    delimiters = str(config.get("delimiters", ""))
    error_handling = str(config.get("error_handling", "Last"))
    output = input_frame.copy()
    names = _column_names(root_name, num_fields)
    values_by_column = {name: [] for name in names}

    for value in input_frame[field].tolist():
        parts = _split_value(value, delimiters)
        if len(parts) > num_fields and error_handling.lower() == "last":
            parts = [*parts[: num_fields - 1], delimiters[:1].join(parts[num_fields - 1:])]
        padded = [*parts[:num_fields], *([""] * max(0, num_fields - len(parts)))]
        for name, part in zip(names, padded):
            values_by_column[name].append(part)
    for name in names:
        output[name] = values_by_column[name]
    return output


def _split_to_rows(input_frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    field = str(config.get("field", ""))
    delimiters = str(config.get("delimiters", ""))
    rows: list[dict[str, Any]] = []
    for row in input_frame.to_dict("records"):
        parts = _split_value(row[field], delimiters)
        for part in parts:
            next_row = dict(row)
            next_row[field] = part
            rows.append(next_row)
    return pd.DataFrame(rows, columns=input_frame.columns)


def texttocolumns_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("TextToColumns tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    field = str(config.get("field", ""))
    ensure_fields_exist(input_frame, [field])

    flags = int(config.get("flags", 0))
    if "split_to_rows" in config:
        output = split_imported_field(input_frame, *imported_split_options(config), warn=context.record_warning)
    else:
        output = _split_to_rows(input_frame, config) if flags & 1 else _split_to_columns(input_frame, config)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="TextToColumns",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "field": field,
            "root_name": config.get("root_name", field),
            "delimiters": config.get("delimiters", ""),
            "num_fields": config.get("num_fields", 1),
            "flags": flags,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class TextToColumnsTool(BaseTool):
    tool_type = "TextToColumns"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return texttocolumns_tool(inputs, config, context)
