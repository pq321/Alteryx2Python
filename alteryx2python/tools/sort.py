from __future__ import annotations

from decimal import Decimal
import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


_DECIMAL_TEXT = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")
_DIGIT_RUN = re.compile(r"([0-9]+)")


def sort_locale_name(locale):
    from locale import windows_locale

    try:
        lcid = int(locale or 0)
        return windows_locale[lcid].replace("_", "-") if lcid else None
    except (TypeError, ValueError, KeyError) as error:
        raise ValueError(f"Unsupported Sort locale: {locale!r}") from error


def _windows_collation(locale):
    import ctypes
    from ctypes import wintypes
    from functools import cache

    if not hasattr(ctypes, "WinDLL"):
        raise NotImplementedError("Dictionary Sort for text requires Windows locale collation")
    map_string = ctypes.WinDLL("kernel32", use_last_error=True).LCMapStringEx
    map_string.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPCWSTR, ctypes.c_int, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    )
    map_string.restype = ctypes.c_int
    map_sort_key = 0x00000400  # LCMAP_SORTKEY

    @cache
    def key(value):
        length = len(value.encode("utf-16-le", errors="surrogatepass")) // 2 or 1
        size = map_string(locale, map_sort_key, value, length, None, 0, None, None, 0)
        if not size:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(size)
        if not map_string(locale, map_sort_key, value, length, buffer, size, None, None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.raw

    return key


def _dictionary_key(value, collate):
    if _DECIMAL_TEXT.fullmatch(value):
        return ((0, Decimal(value)),)
    return tuple((0, Decimal(part)) if part.isascii() and part.isdecimal() else (1, collate(part))
                 for part in _DIGIT_RUN.split(value) if part)


def sort_binary_frame(frame, fields, ascending):
    for field, forward in reversed(list(zip(fields, ascending))):
        frame = frame.sort_values(field, ascending=forward, kind="stable",
                                  na_position="first" if forward else "last")
    return frame.reset_index(drop=True)


def sort_frame(frame, fields, ascending, locale=None):
    """Sort by the saved keys, leaving original fields and stable ties intact."""
    collate = None

    def collate_text(value):
        nonlocal collate
        if collate is None:
            collate = _windows_collation(locale)
        return collate(value)

    def dictionary_keys(series):
        present = series.dropna()
        if present.empty or not all(isinstance(value, str) for value in present):
            return series
        return series.map(lambda value: _dictionary_key(value, collate_text), na_action="ignore")

    # Sort least-significant keys first to apply null precedence per direction.
    for field, forward in reversed(list(zip(fields, ascending))):
        frame = frame.sort_values(field, ascending=forward, kind="stable",
                                  na_position="first" if forward else "last",
                                  key=dictionary_keys if locale else None)
    return frame.reset_index(drop=True)


def sort_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Sort tool requires an Input anchor")
    input_frame = inputs["Input"]
    sort_fields = [field for field in config.get("sort_fields", []) if isinstance(field, dict)]
    if not sort_fields:
        raise ValueError("Sort tool config requires sort_fields")

    fields = [str(field.get("field", "")) for field in sort_fields]
    ensure_fields_exist(input_frame, fields)
    ascending = [_is_ascending(str(field.get("order", "Ascending"))) for field in sort_fields]
    locale = sort_locale_name(config.get("sort_locale"))
    output = sort_frame(input_frame, fields, ascending, locale)

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Sort",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "sort_fields": sort_fields,
            "sort_locale": config.get("sort_locale", "0"),
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


def _is_ascending(order: str) -> bool:
    normalized = order.strip().lower()
    if normalized == "ascending":
        return True
    if normalized == "descending":
        return False
    raise ValueError(f"Unsupported Sort order: {order}")


class SortTool(BaseTool):
    tool_type = "Sort"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return sort_tool(inputs, config, context)
