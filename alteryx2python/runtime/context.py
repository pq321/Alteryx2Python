from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from alteryx2python.runtime.trace import AnchorTrace, NodeExecutionTrace


@dataclass(slots=True)
class WorkflowContext:
    runtime_config: dict[str, Any] | None = None
    traces: list[NodeExecutionTrace] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def record_warning(self, message: str) -> None:
        self.warnings.append(message)

    def record_error(self, message: str) -> None:
        self.errors.append(message)

    def record_diagnostic(self, diagnostic: dict[str, Any]) -> None:
        self.diagnostics.append(diagnostic)

    def record_node(
        self,
        *,
        node_id: str,
        tool_type: str,
        source_tool_id: str | None,
        inputs: dict[str, pd.DataFrame],
        outputs: dict[str, pd.DataFrame],
        status: str,
        config: dict[str, Any],
    ) -> None:
        self.traces.append(
            NodeExecutionTrace(
                node_id=node_id,
                tool_type=tool_type,
                source_tool_id=source_tool_id,
                status=status,
                config=config,
                inputs={anchor: AnchorTrace.from_frame(frame) for anchor, frame in inputs.items()},
                outputs={anchor: AnchorTrace.from_frame(frame) for anchor, frame in outputs.items()},
                warnings=list(self.warnings),
                errors=list(self.errors),
            )
        )

    def execution_report(self) -> dict[str, Any]:
        return {
            "runtime_config": self.runtime_config or {},
            "traces": [trace.to_dict() for trace in self.traces],
            "warnings": self.warnings,
            "errors": self.errors,
            "diagnostics": self.diagnostics,
        }
