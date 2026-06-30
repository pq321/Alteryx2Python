from __future__ import annotations

import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


_COORD_PAIR_RE = re.compile(r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("Generalize tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _dedupe_coordinate_runs(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    matches = list(_COORD_PAIR_RE.finditer(value))
    if not matches:
        return value
    pieces: list[str] = []
    last_end = 0
    previous_pair: tuple[str, str] | None = None
    for match in matches:
        pair = (match.group(1), match.group(2))
        if pair == previous_pair:
            last_end = match.end()
            continue
        pieces.append(value[last_end : match.start()])
        pieces.append(match.group(0))
        last_end = match.end()
        previous_pair = pair
    pieces.append(value[last_end:])
    return "".join(pieces)


def generalize_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    spatial_field = str(config.get("spatial_field", ""))
    ensure_fields_exist(input_frame, [spatial_field])

    output_field = str(config.get("output_field", "") or "SpatialObj_Generalize")
    include_source = bool(config.get("include_source", True))
    output = input_frame.copy() if include_source else input_frame.drop(columns=[spatial_field]).copy()
    output[output_field] = [_dedupe_coordinate_runs(value) for value in input_frame[spatial_field]]

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Generalize",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "spatial_field": spatial_field,
            "output_field": output_field,
            "include_source": include_source,
            "threshold": config.get("threshold", ""),
            "units": config.get("units", ""),
            "layerwise": bool(config.get("layerwise", False)),
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class GeneralizeTool(BaseTool):
    tool_type = "Generalize"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return generalize_tool(inputs, config, context)
