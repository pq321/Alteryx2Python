from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import compare_schema_snapshots, snapshot_schema


@dataclass(slots=True, frozen=True)
class ValueDifference:
    row_index: int
    column: str
    left: Any
    right: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_index": self.row_index,
            "column": self.column,
            "left": self.left,
            "right": self.right,
        }


@dataclass(slots=True)
class DataFrameDiff:
    matches: bool
    issues: list[str] = field(default_factory=list)
    value_differences: list[ValueDifference] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "matches": self.matches,
            "issues": list(self.issues),
            "value_differences": [
                difference.to_dict() for difference in self.value_differences
            ],
        }


def compare_dataframes(left: pd.DataFrame, right: pd.DataFrame) -> DataFrameDiff:
    issues = compare_schema_snapshots(snapshot_schema(left), snapshot_schema(right))
    value_differences: list[ValueDifference] = []
    if not issues:
        for row_index, (left_row, right_row) in enumerate(zip(left.itertuples(index=False), right.itertuples(index=False))):
            for column, left_value, right_value in zip(left.columns, left_row, right_row):
                if pd.isna(left_value) and pd.isna(right_value):
                    continue
                if left_value != right_value:
                    value_differences.append(
                        ValueDifference(
                            row_index=row_index,
                            column=str(column),
                            left=left_value,
                            right=right_value,
                        )
                    )
    if value_differences:
        issues.append(f"Value mismatch count: {len(value_differences)}")
    return DataFrameDiff(matches=not issues, issues=issues, value_differences=value_differences)
