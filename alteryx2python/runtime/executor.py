from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from alteryx2python.runtime.node_result import NodeResult

if TYPE_CHECKING:
    from alteryx2python.runtime.context import WorkflowContext
    from alteryx2python.tools.registry import ToolMetadata


def run_tool_node(
    metadata: "ToolMetadata",
    inputs: dict[str, pd.DataFrame],
    config: dict[str, object],
    context: "WorkflowContext",
) -> NodeResult:
    outputs = metadata.function(inputs, config, context)
    trace = context.traces[-1] if context.traces else None
    return NodeResult(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=metadata.tool_type,
        outputs=outputs,
        trace=trace,
    )