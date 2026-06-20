from __future__ import annotations

import re
from typing import Any

import pandas as pd

from alteryx2python.expressions.errors import UnsupportedExpressionError


def _is_null(value: Any) -> bool:
    return bool(pd.isna(value))


def _is_empty(value: Any) -> bool:
    return value is None or bool(pd.isna(value)) or str(value) == ""


def _replace(value: Any, old: Any, new: Any) -> str:
    return ("" if value is None else str(value)).replace(str(old), str(new))


def _regex_replace(value: Any, pattern: str, replacement: str) -> str:
    return re.sub(pattern, replacement, "" if value is None else str(value))


def _regex_match(value: Any, pattern: str) -> bool:
    return re.match(pattern, "" if value is None else str(value)) is not None


def _round(value: Any, digits: Any = 0) -> float:
    return round(float(value), int(digits))


def _starts_with(value: Any, prefix: Any) -> bool:
    return ("" if value is None else str(value)).startswith(str(prefix))


def _to_string(value: Any) -> str:
    if value is None or bool(pd.isna(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _pad_left(value: Any, width: Any, fill: Any = " ") -> str:
    fill_text = str(fill)
    if len(fill_text) != 1:
        raise UnsupportedExpressionError("PadLeft fill argument must be one character")
    return str(value).rjust(int(width), fill_text)


def _titlecase(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).title()


def _uppercase(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).upper()


FUNCTION_REGISTRY = {
    "ISEMPTY": _is_empty,
    "ISNULL": _is_null,
    "PADLEFT": _pad_left,
    "REPLACE": _replace,
    "REGEX_MATCH": _regex_match,
    "REGEX_REPLACE": _regex_replace,
    "ROUND": _round,
    "STARTSWITH": _starts_with,
    "TITLECASE": _titlecase,
    "TOSTRING": _to_string,
    "UPPERCASE": _uppercase,
}


def call_function(name: str, args: list[Any]) -> Any:
    function = FUNCTION_REGISTRY.get(name.upper())
    if function is None:
        raise UnsupportedExpressionError(f"Unsupported expression function: {name}")
    return function(*args)
