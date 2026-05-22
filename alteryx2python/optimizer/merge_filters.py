from __future__ import annotations

from alteryx2python.ir.models import WorkflowIR
from alteryx2python.optimizer.base_optimizer import BaseOptimizer


class MergeFiltersOptimizer(BaseOptimizer):
    def optimize(self, workflow: WorkflowIR) -> WorkflowIR:
        self.ensure_enabled()
        return workflow