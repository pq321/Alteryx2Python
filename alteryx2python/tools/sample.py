from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _apply_grouped(frame: pd.DataFrame, group_fields: list[str], sampler) -> pd.DataFrame:
    if not group_fields:
        return sampler(frame)
    missing = [field for field in group_fields if field not in frame.columns]
    if missing:
        raise KeyError(f"Missing Sample group fields: {', '.join(missing)}")
    pieces = [sampler(group) for _, group in frame.groupby(group_fields, sort=False, dropna=False)]
    if not pieces:
        return frame.iloc[0:0].copy()
    return pd.concat(pieces, ignore_index=True)


def _sample_frame(frame: pd.DataFrame, mode: str, n: int) -> pd.DataFrame:
    if n < 0:
        raise ValueError("Sample N must be non-negative")
    normalized = mode.lower()
    if normalized == "first":
        return frame.head(n).copy()
    if normalized == "last":
        return frame.tail(n).copy()
    if normalized in {"sample", "everynth"}:
        if n == 0:
            return frame.iloc[0:0].copy()
        return frame.iloc[::n].copy()
    if normalized == "random":
        return frame.sample(n=min(n, len(frame.index)), random_state=0).sort_index().copy()
    if normalized == "npercent":
        count = int(len(frame.index) * (n / 100))
        return frame.head(count).copy()
    raise NotImplementedError(f"Sample mode is not supported: {mode}")


def sample_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Sample tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    mode = str(config.get("mode", "First"))
    n = int(config.get("n", 0))
    group_fields = [str(field) for field in config.get("group_fields", [])]

    output = _apply_grouped(input_frame, group_fields, lambda frame: _sample_frame(frame, mode, n))
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Sample",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "mode": mode,
            "n": n,
            "group_fields": group_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class SampleTool(BaseTool):
    tool_type = "Sample"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return sample_tool(inputs, config, context)
