from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from alteryx2python.expressions.errors import UnsupportedExpressionError


def _is_null(value: Any) -> bool:
    return bool(pd.isna(value))


def _is_empty(value: Any) -> bool:
    return value is None or bool(pd.isna(value)) or str(value) == ""


def _replace(value: Any, old: Any, new: Any) -> str:
    return ("" if value is None else str(value)).replace(str(old), str(new))


def _left(value: Any, count: Any) -> str:
    return ("" if value is None else str(value))[: int(count)]


def _right(value: Any, count: Any) -> str:
    text = "" if value is None else str(value)
    return text[-int(count):]


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


def _datetime_add(value: Any, amount: Any, unit: Any) -> str:
    parsed = pd.to_datetime(value)
    normalized_unit = str(unit).lower()
    count = int(amount)
    if normalized_unit in {"day", "days"}:
        result = parsed + timedelta(days=count)
    elif normalized_unit in {"hour", "hours"}:
        result = parsed + timedelta(hours=count)
    elif normalized_unit in {"minute", "minutes"}:
        result = parsed + timedelta(minutes=count)
    elif normalized_unit in {"second", "seconds"}:
        result = parsed + timedelta(seconds=count)
    else:
        raise UnsupportedExpressionError(f"Unsupported DateTimeAdd unit: {unit}")
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return result.strftime("%Y-%m-%d")
    if isinstance(result, datetime):
        return result.isoformat()
    return str(result)


def _datetime_diff(end_value: Any, start_value: Any, unit: Any) -> int | None:
    if end_value is None or start_value is None or bool(pd.isna(end_value)) or bool(pd.isna(start_value)):
        return None
    end = pd.to_datetime(end_value)
    start = pd.to_datetime(start_value)
    seconds = (end - start).total_seconds()
    normalized_unit = str(unit).lower()
    if normalized_unit in {"second", "seconds"}:
        return int(seconds)
    if normalized_unit in {"minute", "minutes"}:
        return int(seconds / 60)
    if normalized_unit in {"hour", "hours"}:
        return int(seconds / 3600)
    if normalized_unit in {"day", "days"}:
        return int(seconds / 86400)
    raise UnsupportedExpressionError(f"Unsupported DateTimeDiff unit: {unit}")


def _average(*values: Any) -> float | None:
    numeric_values = [float(value) for value in values if value is not None and not bool(pd.isna(value))]
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _trim(value: Any, chars: Any = None) -> str:
    text = "" if value is None or bool(pd.isna(value)) else str(value)
    if chars is None:
        return text.strip()
    return text.strip(str(chars))


def _null() -> None:
    return None


FUNCTION_REGISTRY = {
    "DATETIMEADD": _datetime_add,
    "DATETIMEDIFF": _datetime_diff,
    "AVERAGE": _average,
    "ISEMPTY": _is_empty,
    "ISNULL": _is_null,
    "LEFT": _left,
    "PADLEFT": _pad_left,
    "REPLACE": _replace,
    "REGEX_MATCH": _regex_match,
    "REGEX_REPLACE": _regex_replace,
    "ROUND": _round,
    "RIGHT": _right,
    "STARTSWITH": _starts_with,
    "TITLECASE": _titlecase,
    "TRIM": _trim,
    "TOSTRING": _to_string,
    "NULL": _null,
    "UPPERCASE": _uppercase,
}


def call_function(name: str, args: list[Any]) -> Any:
    function = FUNCTION_REGISTRY.get(name.upper())
    if function is None:
        raise UnsupportedExpressionError(f"Unsupported expression function: {name}")
    return function(*args)
