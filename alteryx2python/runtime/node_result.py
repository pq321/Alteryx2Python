from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from alteryx2python.runtime.trace import NodeExecutionTrace


@dataclass(slots=True)
class NodeResult:
    node_id: str
    tool_type: str
    outputs: dict[str, pd.DataFrame]
    trace: NodeExecutionTrace | None = None