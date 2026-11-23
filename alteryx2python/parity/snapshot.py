from __future__ import annotations

import base64
from collections import Counter, defaultdict, deque
import json
import math
from io import BytesIO
from datetime import date, datetime, time
from decimal import Decimal
from numbers import Integral, Real
from fractions import Fraction
from typing import Any

import pandas as pd


class SnapshotEncodingError(TypeError):
    """Capture/representation failure is not a user workflow's semantic error."""


def encode_value(value: Any) -> dict[str, Any]:
    """Lossless JSON cells: never conflate null, empty, zero and false."""
    if value is None or value is pd.NA or value is pd.NaT:
        return {"kind": "null"}
    if isinstance(value, bool):
        return {"kind": "bool", "value": value}
    if isinstance(value, Integral):
        return {"kind": "int", "value": str(value)}
    if isinstance(value, Real):
        number = float(value)
        return {"kind": "float", "value": "nan" if math.isnan(number) else number.hex()}
    if isinstance(value, Decimal):
        return {"kind": "decimal", "value": str(value)}
    if isinstance(value, str):
        return {"kind": "string", "value": value}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "kind": "bytes",
            "value": base64.b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, datetime):
        return {"kind": "datetime", "value": value.isoformat()}
    if isinstance(value, (date, time)):
        return {"kind": type(value).__name__, "value": value.isoformat()}
    if type(value).__module__.startswith("PIL."):
        from PIL.Image import Image

        if isinstance(value, Image):
            stream = BytesIO()
            value.save(stream, format="PNG")
            return {
                "kind": "image",
                "width": value.width,
                "height": value.height,
                "mode": value.mode,
                "png_base64": base64.b64encode(stream.getvalue()).decode("ascii"),
            }
    # Numpy scalars returned by extension arrays.
    if hasattr(value, "item"):
        return encode_value(value.item())
    raise SnapshotEncodingError(f"Unsupported parity cell type: {type(value).__name__}")


def frame_snapshot(frame: pd.DataFrame) -> dict[str, Any]:
    schema = frame.attrs.get("alteryx_schema")
    return {
        "columns": [str(column) for column in frame.columns],
        "schema": schema,
        "python_dtypes": [str(dtype) for dtype in frame.dtypes],
        "rows": [
            [
                {"kind": "null"}
                if isinstance(cell, Real) and math.isnan(float(cell))
                else encode_value(cell)
                for cell in row
            ]
            for row in frame.itertuples(index=False, name=None)
        ],
    }


def compare_snapshots(
    expected: dict[str, Any], actual: dict[str, Any], *, profile: str = "behavioral",
    align_columns: bool = False, align_rows: bool = False,
) -> dict[str, Any]:
    differences: list[dict[str, Any]] = []
    order_differences = []
    left_columns, right_columns = expected.get("columns"), actual.get("columns")
    left_rows, right_rows = expected.get("rows", []), actual.get("rows", [])
    columns_match = left_columns == right_columns
    if align_columns and not columns_match and isinstance(left_columns, list) and isinstance(right_columns, list):
        if Counter(left_columns) == Counter(right_columns) and all(len(row) == len(right_columns) for row in right_rows):
            indexes = defaultdict(deque)
            for index, name in enumerate(right_columns):
                indexes[name].append(index)
            order = [indexes[name].popleft() for name in left_columns]
            right_rows = [[row[index] for index in order] for row in right_rows]
            columns_match = True
            order_differences.append("columns")
    if not columns_match:
        differences.append({
            "dimension": "columns", "expected": left_columns, "actual": right_columns,
        })
    rows_equal = left_rows == right_rows
    if not rows_equal and len(left_rows) == len(right_rows):
        rows_equal = all(
            len(left) == len(right)
            and all(_equal_cell(a, b, profile) for a, b in zip(left, right))
            for left, right in zip(left_rows, right_rows)
        )
    if (align_columns or align_rows) and columns_match and not rows_equal and len(left_rows) == len(right_rows):
        def row_counts(rows):
            return Counter(tuple(cell_comparison_key(cell, profile=profile) for cell in row) for row in rows)

        if row_counts(left_rows) == row_counts(right_rows):
            order_differences.append("rows")
            rows_equal = align_rows
    if not rows_equal:
        differences.append({"dimension": "rows"})
    missing_schema = not _complete_schema(expected) or not _complete_schema(actual)
    if (
        profile == "strict"
        and not missing_schema
        and expected["schema"] != actual["schema"]
    ):
        differences.append(
            {
                "dimension": "schema",
                "expected": expected["schema"],
                "actual": actual["schema"],
            }
        )
    value_differences = []
    if columns_match and not rows_equal:
        for row_index, (left, right) in enumerate(
            zip(left_rows, right_rows)
        ):
            for column, left_cell, right_cell in zip(
                left_columns or [], left, right
            ):
                if not _equal_cell(left_cell, right_cell, profile):
                    value_differences.append(
                        {
                            "row": row_index,
                            "column": column,
                            "expected": left_cell,
                            "actual": right_cell,
                        }
                    )
                    if len(value_differences) == 20:
                        break
            if len(value_differences) == 20:
                break
    return {
        "status": "mismatch"
        if differences
        else "incomplete"
        if profile == "strict" and missing_schema
        else "match",
        "values_match": not any(
            item["dimension"] in {"columns", "rows"} for item in differences
        ),
        "schema_verified": not missing_schema,
        "differences": differences,
        "value_differences": value_differences,
        **({"order_differences": order_differences} if order_differences else {}),
        "expected_row_count": len(expected.get("rows", [])),
        "actual_row_count": len(actual.get("rows", [])),
    }


_NUMERIC_KINDS = {"int", "float", "decimal"}


def cell_comparison_key(cell: dict[str, Any], *, profile: str = "behavioral") -> str:
    if profile != "strict" and cell.get("kind") in _NUMERIC_KINDS:
        try:
            value = float.fromhex(cell["value"]) if cell["kind"] == "float" else Decimal(cell["value"])
            return f"numeric:{Fraction(value)}"
        except (ValueError, OverflowError):
            pass
    return json.dumps(cell, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _equal_cell(left: dict[str, Any], right: dict[str, Any], profile: str) -> bool:
    return left == right or (
        profile != "strict"
        and left.get("kind") in _NUMERIC_KINDS
        and right.get("kind") in _NUMERIC_KINDS
        and cell_comparison_key(left) == cell_comparison_key(right)
    )


def _complete_schema(snapshot: dict[str, Any]) -> bool:
    schema = snapshot.get("schema")
    columns = snapshot.get("columns")
    rows = snapshot.get("rows")
    return (
        isinstance(schema, list)
        and isinstance(columns, list)
        and isinstance(rows, list)
        and len(schema) == len(columns)
        and all(
            isinstance(field, dict)
            and field.get("name") == name
            and field.get("type")
            and {"name", "type", "size", "scale"} <= field.keys()
            and (
                field["size"] is not None
                or field["type"]
                not in {"String", "WString", "V_String", "V_WString", "FixedDecimal"}
            )
            for field, name in zip(schema, columns)
        )
        and all(isinstance(row, list) and len(row) == len(columns) for row in rows)
    )
