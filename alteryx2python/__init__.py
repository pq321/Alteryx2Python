"""Core package for Alteryx-to-Python migration."""

__all__ = ["SelectTool", "TOOL_REGISTRY", "WorkflowContext", "select_tool"]


def __getattr__(name: str):
    if name == "WorkflowContext":
        from alteryx2python.runtime.context import WorkflowContext

        return WorkflowContext
    if name == "TOOL_REGISTRY":
        from alteryx2python.tools.registry import TOOL_REGISTRY

        return TOOL_REGISTRY
    if name == "SelectTool":
        from alteryx2python.tools.select import SelectTool

        return SelectTool
    if name == "select_tool":
        from alteryx2python.tools.select import select_tool

        return select_tool
    raise AttributeError(f"module 'alteryx2python' has no attribute {name!r}")
