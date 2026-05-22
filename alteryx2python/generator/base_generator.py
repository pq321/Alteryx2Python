from __future__ import annotations

from abc import ABC, abstractmethod

from alteryx2python.ir.models import WorkflowIR


class BaseGenerator(ABC):
    @abstractmethod
    def generate(self, workflow: WorkflowIR) -> str:
        raise NotImplementedError