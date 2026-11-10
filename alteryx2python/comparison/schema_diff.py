from __future__ import annotations

from typing import Iterable, TypedDict

import pandas as pd


class SchemaSnapshot(TypedDict):
    columns: list[str]
    dtypes: dict[str, str]
    row_count: int


def ensure_fields_exist(frame: pd.DataFrame, field_names: Iterable[str]) -> None:
    missing = [field_name for field_name in field_names if field_name not in frame.columns]
    if missing:
        missing_text = ", ".join(missing)
        raise KeyError(f"Missing input fields: {missing_text}")


def snapshot_schema(frame: pd.DataFrame) -> SchemaSnapshot:
    return {
        "columns": list(frame.columns),
        "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
        "row_count": int(len(frame.index)),
    }


def normalize_dtype(dtype: str) -> str:
    """Treat pandas object strings and the pandas 3 str dtype as equivalent.

    CSV oracles read with type inference may report either representation for
    the same textual column, so schema comparison normalizes them.
    """
    if dtype in ("object", "str"):
        return "string"
    return dtype


def compare_schema_snapshots(left: SchemaSnapshot, right: SchemaSnapshot) -> list[str]:
    issues: list[str] = []
    if left["columns"] != right["columns"]:
        issues.append("Column order or names differ")
    left_dtypes = {column: normalize_dtype(dtype) for column, dtype in left["dtypes"].items()}
    right_dtypes = {column: normalize_dtype(dtype) for column, dtype in right["dtypes"].items()}
    if left_dtypes != right_dtypes:
        issues.append("Column dtypes differ")
    if left["row_count"] != right["row_count"]:
        issues.append("Row counts differ")
    return issues