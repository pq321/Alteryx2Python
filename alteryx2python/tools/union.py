from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def union_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if not inputs:
        raise KeyError("Union tool requires at least one input anchor")
    mode = str(config.get("mode", "ByName"))
    if mode.lower() != "byname":
        raise NotImplementedError("Union currently supports only ByName mode")

    ordered_frames = [inputs[anchor] for anchor in sorted(inputs)]
    columns = list(dict.fromkeys(column for frame in ordered_frames for column in frame.columns))
    aligned = [frame.reindex(columns=columns) for frame in ordered_frames]
    output = pd.concat(aligned, ignore_index=True).astype(object).where(pd.notna(pd.concat(aligned, ignore_index=True)), None)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Union",
        source_tool_id=config.get("source_tool_id"),
        inputs=inputs,
        outputs=outputs,
        status="success",
        config={
            "mode": mode,
            "input_schema": {anchor: snapshot_schema(frame) for anchor, frame in inputs.items()},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class UnionTool(BaseTool):
    tool_type = "Union"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return union_tool(inputs, config, context)
