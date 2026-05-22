"""Backward-compatible Select tool export.

New code should import from ``alteryx2python.tools.select``.
"""

from alteryx2python.tools.select import SUPPORTED_TYPE_MAP, SelectTool, select_tool

__all__ = ["SUPPORTED_TYPE_MAP", "SelectTool", "select_tool"]