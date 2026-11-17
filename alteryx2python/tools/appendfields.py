from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.field_contracts import coerce_field


def _frame(inputs: dict[str, pd.DataFrame], anchor: str) -> pd.DataFrame:
    if anchor not in inputs:
        raise KeyError(f"AppendFields tool requires a {anchor} anchor")
    frame = inputs[anchor]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{anchor} anchor must contain a pandas DataFrame")
    return frame


def append_projection(target_columns, source_columns, select_fields, order_changed):
    """Resolve qualified field identities before assigning output names."""
    incoming = {}
    unqualified = {}
    for origin, columns in (("Target", target_columns), ("Source", source_columns)):
        for column in columns:
            reference = f"{origin}_{column}"
            incoming[reference] = origin, column
            unqualified.setdefault(column, reference)
    selected_fields = {}
    for field in select_fields:
        reference = field["source"]
        if reference != "*Unknown" and not reference.startswith(("Target_", "Source_")):
            reference = unqualified.get(reference, reference)
        selected_fields[reference] = field

    wildcard = selected_fields.get("*Unknown")
    include_unknown = not select_fields or (wildcard is not None and wildcard.get("selected", True))
    unknown = [reference for reference in incoming if reference not in selected_fields] if include_unknown else []
    ordered = []
    if order_changed and selected_fields:
        for reference in selected_fields:
            ordered.extend(unknown if reference == "*Unknown" else [reference])
    else:
        ordered = [reference for reference in incoming if include_unknown or reference in selected_fields]

    projection, used_names = [], set()
    for reference in ordered:
        field = selected_fields.get(reference, {})
        if reference not in incoming or not field.get("selected", True):
            continue
        origin, column = incoming[reference]
        name = field.get("rename") or column
        if name.casefold() in used_names:
            name = f"{origin}_{name}"
            stem, suffix = name, 2
            while name.casefold() in used_names:
                name = f"{stem}{suffix}"
                suffix += 1
        used_names.add(name.casefold())
        projection.append((field.get("source", reference), origin, column, name))
    return projection


def append_rows(targets, source, select_fields, order_changed):
    projection = append_projection(targets.columns, source.columns, select_fields, order_changed)
    source_records = source.to_dict("records")
    rows = [
        [target[column] if origin == "Target" else record[column] for _, origin, column, _ in projection]
        for target in targets.to_dict("records")
        for record in source_records
    ]
    return pd.DataFrame(rows, columns=[name for _, _, _, name in projection]), {
        reference: name for reference, _, _, name in projection
    }


def appendfields_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    targets = _frame(inputs, "Targets")
    source = _frame(inputs, "Source")
    mode = str(config.get("cartesian_mode", "Error"))
    if mode == "Error" and len(targets.index) * len(source.index) > max(len(targets.index), len(source.index)):
        raise ValueError("AppendFields CartesianMode=Error rejects many-to-many append")

    fields = config.get("select_fields", [])
    output, names = append_rows(targets, source, fields, config.get("order_changed", False))
    for field in fields:
        reference, dtype = field["source"], field.get("dtype")
        if dtype and reference in names and reference != "*Unknown":
            name = names[reference]
            output[name] = coerce_field(output[name], dtype, field.get("size"))
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="AppendFields",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Targets": targets, "Source": source},
        outputs=outputs,
        status="success",
        config={
            "cartesian_mode": mode,
            "input_schema": {"Targets": snapshot_schema(targets), "Source": snapshot_schema(source)},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class AppendFieldsTool(BaseTool):
    tool_type = "AppendFields"
    input_anchors = ("Targets", "Source")
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return appendfields_tool(inputs, config, context)
