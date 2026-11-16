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

    ordered_anchors = _ordered_input_anchors(inputs, config)
    ordered_frames = [inputs[anchor] for anchor in ordered_anchors]
    if mode.lower() == "byname":
        columns = list(dict.fromkeys(column for frame in ordered_frames for column in frame.columns))
        aligned = [frame.reindex(columns=columns) for frame in ordered_frames]
    elif mode.lower() == "bypos":
        columns = _bypos_output_columns(ordered_frames, config)
        aligned = []
        for frame in ordered_frames:
            renamed = frame.copy()
            renamed.columns = columns[: len(renamed.columns)]
            aligned.append(renamed.reindex(columns=columns))
    elif mode.lower() in {"manual", "manualdelayed"}:
        aligned = _align_manual(ordered_anchors, inputs, config)
    else:
        raise NotImplementedError(f"Unsupported Union mode: {mode}")
    concatenated = pd.concat(aligned, ignore_index=True)
    output = concatenated.astype(object).where(pd.notna(concatenated), None)
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


def _align_manual(anchors, inputs, config):
    definitions = config.get("manual_inputs", {})
    connections = config.get("input_connection_names", {})
    labels = {}
    mappings = []
    for index, anchor in enumerate(anchors, 1):
        connection = connections.get(anchor) or f"#{index}"
        if connection not in definitions:
            raise ValueError(f"Union has no saved manual mapping for {connection}")
        small = {}
        frame = inputs[anchor]
        for field in definitions[connection]:
            column, name = field["column"], field["name"]
            if column < 1:
                continue
            if column in small:
                raise ValueError(f"Union input {connection} maps multiple fields to column {column}")
            if name not in frame:
                raise ValueError(f"Union input {connection} has no field {name!r}")
            labels.setdefault(column, name)
            small[column] = frame[name].astype(object)
        mappings.append((frame.index, small))
    columns = sorted(labels)
    result = []
    for index, mapping in mappings:
        frame = pd.DataFrame(mapping, index=index).reindex(columns=columns)
        frame.columns = [labels[column] for column in columns]
        result.append(frame)
    return result


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


def _bypos_output_columns(ordered_frames: list[pd.DataFrame], config: dict[str, Any]) -> list[str]:
    expected_columns = _expected_output_columns(config.get("expected_output_schema"))
    if expected_columns:
        return expected_columns
    return list(ordered_frames[0].columns)


def _expected_output_columns(schema: Any) -> list[str]:
    if not isinstance(schema, dict):
        return []
    if "fields" in schema:
        return _field_names(schema.get("fields"))
    output_schema = schema.get("Output")
    if isinstance(output_schema, dict):
        return _field_names(output_schema.get("fields"))
    return []


def _field_names(fields: Any) -> list[str]:
    if not isinstance(fields, list):
        return []
    return [str(field["name"]) for field in fields if isinstance(field, dict) and "name" in field]


def _ordered_input_anchors(inputs: dict[str, pd.DataFrame], config: dict[str, Any]) -> list[str]:
    input_connection_names = config.get("input_connection_names")
    output_order = [str(name) for name in config.get("output_order", []) if name]
    if not isinstance(input_connection_names, dict) or not output_order:
        return sorted(inputs)

    order_index = {name: index for index, name in enumerate(output_order)}
    return sorted(
        inputs,
        key=lambda anchor: (
            order_index.get(str(input_connection_names.get(anchor, "")), len(order_index)),
            anchor,
        ),
    )
