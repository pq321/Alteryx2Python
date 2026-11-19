from __future__ import annotations

from decimal import Decimal
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.field_contracts import STRING_TYPES


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
        frames = ordered_frames
    elif mode.lower() == "bypos":
        columns = _bypos_output_columns(ordered_frames, config)
        frames = [rename_union_fields(frame, columns[:len(frame.columns)]) for frame in ordered_frames]
    elif mode.lower() in {"manual", "manualdelayed"}:
        columns, frames = _align_manual(ordered_anchors, inputs, config)
    else:
        raise NotImplementedError(f"Unsupported Union mode: {mode}")
    output = stack_union_rows(frames, columns)
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


# Minimum Designer text widths when a numeric field promotes to variable text.
_NUMERIC_TEXT_WIDTHS = {
    "Byte": 3, "Int16": 6, "Int32": 10, "Int64": 20,
    "Float": 13, "Double": 23, "FixedDecimal": 19, "Bool": 5,
}
_INFERRED_TYPES = {"string": "string", "integer": "Int64", "floating": "Double",
                   "mixed-integer-float": "Double", "decimal": "FixedDecimal", "boolean": "Bool"}


def rename_union_fields(frame, columns):
    renamed = frame.copy(deep=False)
    renamed.columns = columns
    field_names = dict(zip(frame.columns, columns))
    if "alteryx_schema" in frame.attrs:
        renamed.attrs["alteryx_schema"] = [
            {**field, "name": field_names[field["name"]]} for field in frame.attrs["alteryx_schema"]
            if field["name"] in field_names
        ]
    return renamed


def _union_text(value, kind):
    if kind in {"Float", "Double"}:
        text = format(value, ".7g" if kind == "Float" else ".15g")
        mantissa, separator, exponent = text.partition("e")
        if separator and "." not in mantissa:
            return f"{mantissa}.e{exponent}"
        return text
    return format(value, "f") if isinstance(value, Decimal) else str(value)


def stack_union_rows(frames, columns):
    """Reconcile shared text/numeric fields before pandas stacks the rows."""
    schemas = [{field["name"]: field for field in frame.attrs.get("alteryx_schema", [])} for frame in frames]
    converted = [{} for frame in frames]
    promotions = {}
    for column in columns:
        typed = []
        for index, (frame, schema) in enumerate(zip(frames, schemas)):
            if column not in frame:
                continue
            series, declaration = frame[column], schema.get(column, {})
            kind = declaration.get("type")
            if not kind:
                inferred = "string" if isinstance(series.dtype, pd.StringDtype) else pd.api.types.infer_dtype(series, skipna=True)
                kind = _INFERRED_TYPES.get(inferred, inferred)
            if kind != "empty":
                typed.append((index, series, declaration, kind))
        kinds = {kind for _, _, _, kind in typed}
        numeric_types = _NUMERIC_TEXT_WIDTHS.keys()
        if not (kinds & STRING_TYPES and kinds & numeric_types and kinds <= STRING_TYPES | numeric_types):
            continue

        wide = False
        widths = []
        for _, series, declaration, kind in typed:
            if kind in STRING_TYPES:
                wide |= kind in {"WString", "V_WString"}
                size = declaration.get("size") or max((len(str(value)) for value in series.dropna()), default=1)
            elif kind == "FixedDecimal" and declaration.get("size"):
                size = str(declaration["size"]).split(".", 1)[0]
            else:
                size = _NUMERIC_TEXT_WIDTHS[kind]
            widths.append(int(size))
        width = max(widths)
        promotions[column] = {"name": column, "type": "V_WString" if wide else "V_String", "size": width}
        for index, series, _, kind in typed:
            # Nullable Pandas integers can pass through float during map.
            # Boxing first keeps every Int64 digit, even with nulls.
            converted[index][column] = series.astype(object).map(
                lambda value: _union_text(value, kind)[:width], na_action="ignore"
            )

    aligned = []
    for frame, text_columns in zip(frames, converted):
        aligned_frame = frame.reindex(columns=columns)
        for column, values in text_columns.items():
            aligned_frame[column] = values
        aligned.append(aligned_frame)
    combined = pd.concat(aligned, ignore_index=True)
    output = combined.astype(object).where(pd.notna(combined), None)
    if promotions:
        inherited = {field["name"]: field for field in output.attrs.get("alteryx_schema", [])}
        output.attrs["alteryx_schema"] = [
            promotions.get(column, inherited.get(column)) for column in columns
            if column in promotions or column in inherited
        ]
    return output


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
            small[column] = name
        mappings.append((frame, small))
    columns = sorted(labels)
    result = []
    for frame, mapping in mappings:
        positions = sorted(mapping)
        fields = frame.loc[:, [mapping[column] for column in positions]].astype(object)
        result.append(rename_union_fields(fields, [labels[column] for column in positions]))
    return [labels[column] for column in columns], result


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
