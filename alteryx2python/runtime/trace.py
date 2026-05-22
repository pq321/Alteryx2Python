from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(slots=True)
class AnchorTrace:
    row_count: int
    columns: list[str]
    dtypes: dict[str, str]
    null_counts: dict[str, int]

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "AnchorTrace":
        return cls(
            row_count=int(len(frame.index)),
            columns=list(frame.columns),
            dtypes={column: str(dtype) for column, dtype in frame.dtypes.items()},
            null_counts={column: int(count) for column, count in frame.isna().sum().items()},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "columns": self.columns,
            "dtypes": self.dtypes,
            "null_counts": self.null_counts,
        }


@dataclass(slots=True)
class NodeExecutionTrace:
    node_id: str
    tool_type: str
    source_tool_id: str | None
    status: str
    config: dict[str, Any]
    inputs: dict[str, AnchorTrace]
    outputs: dict[str, AnchorTrace]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "tool_type": self.tool_type,
            "source_tool_id": self.source_tool_id,
            "status": self.status,
            "config": self.config,
            "inputs": {anchor: trace.to_dict() for anchor, trace in self.inputs.items()},
            "outputs": {anchor: trace.to_dict() for anchor, trace in self.outputs.items()},
            "warnings": self.warnings,
            "errors": self.errors,
        }