from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def textinput_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    data_inputs = {anchor: frame for anchor, frame in inputs.items() if anchor != "Action"}
    if data_inputs:
        raise ValueError("TextInput does not accept input anchors")

    fields = [str(field) for field in config.get("fields", [])]
    rows = config.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("TextInput config requires rows")
    if not fields:
        raise ValueError("TextInput config requires fields")

    normalized_rows = [_normalize_row(row, fields) for row in rows]
    output = _infer_types(pd.DataFrame(normalized_rows, columns=fields, dtype=object))

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="TextInput",
        source_tool_id=config.get("source_tool_id"),
        inputs={},
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "fields": fields,
            "num_rows": config.get("num_rows"),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


def _normalize_row(row: Any, fields: list[str]) -> list[str | None]:
    if not isinstance(row, list):
        raise ValueError("TextInput row entries must be lists")
    if len(row) != len(fields):
        raise ValueError(f"TextInput row has {len(row)} cells for {len(fields)} fields")
    return [None if value is None else str(value) for value in row]


def _infer_types(frame: pd.DataFrame) -> pd.DataFrame:
    """Infer column dtypes the way the native TextInput engine does.

    A column where every non-empty cell parses as an integer becomes Int64;
    a column where every non-empty cell parses as a float becomes Double;
    anything else stays as object strings. Empty cells become None.
    """
    inferred = frame.copy()
    for column in inferred.columns:
        values = inferred[column]
        non_empty = [value for value in values if value is not None and str(value) != ""]
        if not non_empty:
            continue
        if all(_is_int(value) for value in non_empty):
            if len(non_empty) == len(values):
                inferred[column] = values.map(lambda value: int(str(value)))
            else:
                # nullable Int64 keeps integer cells as integers even when the
                # column contains nulls (pandas would otherwise upcast to float).
                inferred[column] = pd.Series(
                    [_to_int_or_none(value) for value in values], dtype="Int64", index=values.index
                )
        elif all(_is_float(value) for value in non_empty):
            inferred[column] = values.map(_to_float_or_none)
    return inferred


def _to_int_or_none(value: Any) -> Any:
    if value is None or str(value) == "":
        return None
    return int(str(value))


def _to_float_or_none(value: Any) -> Any:
    if value is None or str(value) == "":
        return None
    return float(str(value))


def _is_int(value: Any) -> bool:
    try:
        int(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _is_float(value: Any) -> bool:
    try:
        float(str(value))
        return True
    except (TypeError, ValueError):
        return False


class TextInputTool(BaseTool):
    tool_type = "TextInput"
    input_anchors = ()
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return textinput_tool(inputs, config, context)
