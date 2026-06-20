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


from alteryx2python.tools.crosstab import CrossTabTool, crosstab_tool
from alteryx2python.tools.dbfileinput import DbFileInputTool, dbfileinput_tool
from alteryx2python.tools.dbfileoutput import DbFileOutputTool, dbfileoutput_tool
from alteryx2python.tools.dynamicrename import DynamicRenameTool, dynamicrename_tool
from alteryx2python.tools.filter import FilterTool, filter_tool
from alteryx2python.tools.formula import FormulaTool, formula_tool
from alteryx2python.tools.join import JoinTool, join_tool
from alteryx2python.tools.jsonparse import JSONParseTool, jsonparse_tool
from alteryx2python.tools.recordid import RecordIDTool, recordid_tool
from alteryx2python.tools.select import SelectTool, select_tool
from alteryx2python.tools.sort import SortTool, sort_tool
from alteryx2python.tools.textinput import TextInputTool, textinput_tool
from alteryx2python.tools.transpose import TransposeTool, transpose_tool
from alteryx2python.tools.union import UnionTool, union_tool


TOOL_REGISTRY = ToolRegistry()
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="CrossTab",
        function=crosstab_tool,
        tool_class=CrossTabTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/crosstab.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DbFileInput",
        function=dbfileinput_tool,
        tool_class=DbFileInputTool,
        input_anchors=(),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/dbfileinput.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DbFileOutput",
        function=dbfileoutput_tool,
        tool_class=DbFileOutputTool,
        input_anchors=("Input",),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/dbfileoutput.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DynamicRename",
        function=dynamicrename_tool,
        tool_class=DynamicRenameTool,
        input_anchors=("Targets",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/dynamicrename.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Filter",
        function=filter_tool,
        tool_class=FilterTool,
        input_anchors=("Input",),
        output_anchors=("True", "False"),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/filter.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Join",
        function=join_tool,
        tool_class=JoinTool,
        input_anchors=("Left", "Right"),
        output_anchors=("Join", "Left", "Right"),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/join.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Formula",
        function=formula_tool,
        tool_class=FormulaTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/formula.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="JSONParse",
        function=jsonparse_tool,
        tool_class=JSONParseTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/jsonparse.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="TextInput",
        function=textinput_tool,
        tool_class=TextInputTool,
        input_anchors=(),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/textinput.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Sort",
        function=sort_tool,
        tool_class=SortTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/sort.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Transpose",
        function=transpose_tool,
        tool_class=TransposeTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/transpose.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Union",
        function=union_tool,
        tool_class=UnionTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/union.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="RecordID",
        function=recordid_tool,
        tool_class=RecordIDTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/recordid.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Select",
        function=select_tool,
        tool_class=SelectTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/select.md",
        supports_certification=True,
    )
)
