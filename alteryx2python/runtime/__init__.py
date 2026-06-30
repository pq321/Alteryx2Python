"""Runtime context and execution helpers."""

__all__ = [
    "AnchorTrace",
    "NodeExecutionTrace",
    "NodeResult",
    "WorkflowContext",
    "WorkflowGraphResult",
    "run_tool_node",
    "run_workflow_graph",
]


def __getattr__(name: str):
    if name == "WorkflowContext":
        from alteryx2python.runtime.context import WorkflowContext

        return WorkflowContext
    if name in {"run_tool_node", "run_workflow_graph"}:
        from alteryx2python.runtime.executor import run_tool_node, run_workflow_graph

        return {"run_tool_node": run_tool_node, "run_workflow_graph": run_workflow_graph}[name]
    if name in {"NodeResult", "WorkflowGraphResult"}:
        from alteryx2python.runtime.node_result import NodeResult, WorkflowGraphResult

        return {"NodeResult": NodeResult, "WorkflowGraphResult": WorkflowGraphResult}[name]
    if name in {"AnchorTrace", "NodeExecutionTrace"}:
        from alteryx2python.runtime.trace import AnchorTrace, NodeExecutionTrace

        return {"AnchorTrace": AnchorTrace, "NodeExecutionTrace": NodeExecutionTrace}[name]
    raise AttributeError(f"module 'alteryx2python.runtime' has no attribute {name!r}")
