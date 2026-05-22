"""Backward-compatible compatibility layer.

New code should import from ``alteryx2python.runtime.context``.
"""

from alteryx2python.runtime.context import WorkflowContext

__all__ = ["WorkflowContext"]