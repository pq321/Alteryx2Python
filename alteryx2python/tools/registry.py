from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from alteryx2python.runtime.context import WorkflowContext


ToolFunction = Callable[[dict[str, pd.DataFrame], dict[str, Any], WorkflowContext], dict[str, pd.DataFrame]]


@dataclass(slots=True, frozen=True)
class ToolMetadata:
    tool_type: str
    function: ToolFunction
    tool_class: type[object]
    input_anchors: tuple[str, ...]
    output_anchors: tuple[str, ...]
    maturity: str
    semantics_doc: str
    supports_certification: bool


class ToolRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, ToolMetadata] = {}

    def register(self, metadata: ToolMetadata) -> None:
        if metadata.tool_type in self._registry:
            raise ValueError(f"Tool already registered: {metadata.tool_type}")
        self._registry[metadata.tool_type] = metadata

    def get(self, tool_type: str) -> ToolMetadata:
        return self._registry[tool_type]

    def list_tool_types(self) -> list[str]:
        return sorted(self._registry)


from alteryx2python.tools.select import SelectTool, select_tool


TOOL_REGISTRY = ToolRegistry()
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Select",
        function=select_tool,
        tool_class=SelectTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/select.md",
        supports_certification=False,
    )
)