from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from alteryx2python.runtime.context import WorkflowContext


class BaseTool(ABC):
    tool_type: str = "UNKNOWN"
    input_anchors: tuple[str, ...] = ()
    output_anchors: tuple[str, ...] = ()

    @abstractmethod
    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        raise NotImplementedError