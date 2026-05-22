from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from alteryx2python.ir.models import WorkflowIR


class BaseWorkflowParser(ABC):
    @abstractmethod
    def parse(self, source_path: Path) -> WorkflowIR:
        raise NotImplementedError