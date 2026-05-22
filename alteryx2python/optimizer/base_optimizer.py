from __future__ import annotations

from abc import ABC, abstractmethod

from alteryx2python.ir.models import WorkflowIR


class BaseOptimizer(ABC):
    enabled: bool = False

    def ensure_enabled(self) -> None:
        if not self.enabled:
            raise RuntimeError("Optimizer is disabled for baseline migration")

    @abstractmethod
    def optimize(self, workflow: WorkflowIR) -> WorkflowIR:
        raise NotImplementedError