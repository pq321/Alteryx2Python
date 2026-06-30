from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from alteryx2python.contracts import ContractEvidence
from alteryx2python.runtime.trace import NodeExecutionTrace


@dataclass(slots=True)
class NodeResult:
    node_id: str
    tool_type: str
    outputs: dict[str, pd.DataFrame]
    trace: NodeExecutionTrace | None = None
    contract_evidence: ContractEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "tool_type": self.tool_type,
            "outputs": {
                anchor: {
                    "row_count": len(frame.index),
                    "columns": [str(column) for column in frame.columns],
                    "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
                }
                for anchor, frame in self.outputs.items()
            },
            "trace": self.trace.to_dict() if self.trace is not None else None,
            "contract_evidence": (
                self.contract_evidence.to_dict()
                if self.contract_evidence is not None
                else None
            ),
        }


@dataclass(slots=True)
class WorkflowGraphResult:
    node_results: dict[str, NodeResult]
    execution_order: list[str]
    skipped_node_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_order": list(self.execution_order),
            "skipped_node_ids": list(self.skipped_node_ids),
            "warnings": list(self.warnings),
            "node_results": {
                node_id: result.to_dict()
                for node_id, result in self.node_results.items()
            },
            "contract_evidence": {
                node_id: result.contract_evidence.to_dict()
                for node_id, result in self.node_results.items()
                if result.contract_evidence is not None
            },
        }
