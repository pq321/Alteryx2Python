from __future__ import annotations

from alteryx2python.generator.base_generator import BaseGenerator
from alteryx2python.ir.models import WorkflowIR


class PythonGenerator(BaseGenerator):
    def generate(self, workflow: WorkflowIR) -> str:
        lines = [
            "from alteryx2python.runtime.context import WorkflowContext",
            "",
            "",
            "def run_workflow(runtime_config):",
            "    context = WorkflowContext(runtime_config=runtime_config)",
        ]
        for node in workflow.nodes:
            lines.append(f"    # Node {node.node_id}: {node.tool_type}")
        lines.append("    return context.execution_report()")
        return "\n".join(lines)