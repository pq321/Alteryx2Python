from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from alteryx2python.comparison.dataframe_diff import DataFrameDiff, compare_dataframes


@dataclass(slots=True)
class ToolCertificationReport:
    tool_name: str
    maturity: str
    certification_status: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class DataFrameComparisonReport:
    name: str
    diff: DataFrameDiff
    left_row_count: int
    right_row_count: int
    columns: list[str]

    @property
    def status(self) -> str:
        return "match" if self.diff.matches else "mismatch"

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "left_row_count": self.left_row_count,
            "right_row_count": self.right_row_count,
            "columns": list(self.columns),
            "diff": self.diff.to_dict(),
        }

    def summary(self) -> str:
        if self.diff.matches:
            return f"{self.name}: match ({self.left_row_count} rows, {len(self.columns)} columns)"
        return f"{self.name}: mismatch ({'; '.join(self.diff.issues)})"


def build_dataframe_comparison_report(
    name: str,
    left: pd.DataFrame,
    right: pd.DataFrame,
) -> DataFrameComparisonReport:
    return DataFrameComparisonReport(
        name=name,
        diff=compare_dataframes(left, right),
        left_row_count=len(left.index),
        right_row_count=len(right.index),
        columns=[str(column) for column in left.columns],
    )
