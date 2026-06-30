from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _frame(inputs: dict[str, pd.DataFrame], anchor: str) -> pd.DataFrame:
    if anchor not in inputs:
        raise KeyError(f"ExpectEqual tool requires an {anchor} anchor")
    frame = inputs[anchor]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{anchor} anchor must contain a pandas DataFrame")
    return frame


def expectequal_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    actual = _frame(inputs, "Actual")
    expected = _frame(inputs, "Expected")
    matched = actual.reset_index(drop=True).equals(expected.reset_index(drop=True))
    if not matched:
        context.record_warning("ExpectEqual comparison did not match")
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="ExpectEqual",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Actual": actual, "Expected": expected},
        outputs={},
        status="success",
        config={
            "matched": matched,
            "actual_schema": snapshot_schema(actual),
            "expected_schema": snapshot_schema(expected),
        },
    )
    return {}


class ExpectEqualTool(BaseTool):
    tool_type = "ExpectEqual"
    input_anchors = ("Actual", "Expected")
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return expectequal_tool(inputs, config, context)
