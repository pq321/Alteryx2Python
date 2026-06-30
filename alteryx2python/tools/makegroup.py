from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


class _DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[Any, Any] = {}

    def find(self, item: Any) -> Any:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: Any, right: Any) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def makegroup_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("MakeGroup tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    key_first = str(config.get("key_first", ""))
    key_second = str(config.get("key_second", ""))
    ensure_fields_exist(input_frame, [key_first, key_second])

    groups = _DisjointSet()
    for _, row in input_frame.iterrows():
        groups.union(row[key_first], row[key_second])

    roots: dict[Any, int] = {}
    output = input_frame.copy()
    group_ids: list[int] = []
    for _, row in output.iterrows():
        root = groups.find(row[key_first])
        if root not in roots:
            roots[root] = len(roots) + 1
        group_ids.append(roots[root])
    output["GroupID"] = group_ids

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="MakeGroup",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "key_first": key_first,
            "key_second": key_second,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class MakeGroupTool(BaseTool):
    tool_type = "MakeGroup"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return makegroup_tool(inputs, config, context)
