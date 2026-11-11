from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _cross_aggregate(values, method, separator=','):
    if method == 'first':
        return values[0]
    if method == 'last':
        return values[-1]
    if method == 'count':
        return len(values)
    if method in {'concat', 'concatenate'}:
        return separator.join(str(value) for value in values if value is not None and not pd.isna(value))
    numeric = pd.to_numeric(pd.Series(values), errors='coerce')
    if method == 'sum':
        return numeric.sum(min_count=1)
    if method in {'avg', 'average'}:
        return numeric.mean()
    if method == 'min':
        return numeric.min()
    if method == 'max':
        return numeric.max()
    if method == 'median':
        return numeric.median()
    raise NotImplementedError(f'CrossTab aggregation is unsupported: {method}')


def crosstab_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("CrossTab tool requires an Input anchor")
    input_frame = inputs["Input"]
    group_fields = list(config.get("group_fields", []))
    header_field = str(config.get("header_field", ""))
    data_field = str(config.get("data_field", ""))
    method = str(config.get("method", "First"))
    if method.lower() not in {'first', 'last', 'count', 'sum', 'avg', 'average', 'min', 'max', 'median', 'concat', 'concatenate'}:
        raise NotImplementedError(f'CrossTab aggregation is unsupported: {method}')
    if not header_field or not data_field:
        raise ValueError("CrossTab config requires header_field and data_field")
    ensure_fields_exist(input_frame, [*group_fields, header_field, data_field])

    header_values = list(dict.fromkeys(input_frame[header_field].dropna().astype(str).tolist()))
    grouped_rows: dict[tuple[Any, ...], dict[str, Any]] = {}
    cells = {}
    for row in input_frame.to_dict("records"):
        key = tuple(row[field] for field in group_fields)
        output_row = grouped_rows.setdefault(
            key,
            {field: row[field] for field in group_fields},
        )
        header = row[header_field]
        if pd.isna(header):
            continue
        cells.setdefault((key, str(header)), []).append(row[data_field])

    output_rows = []
    for key, output_row in grouped_rows.items():
        for header in header_values:
            if header in group_fields:
                continue
            values = cells.get((key, header))
            output_row[header] = _cross_aggregate(values, method.lower(), config.get('separator', ',')) if values else None
        output_rows.append(output_row)
    output = pd.DataFrame(output_rows, columns=[*group_fields, *header_values])
    output = output.astype(object).where(pd.notna(output), None)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="CrossTab",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "group_fields": group_fields,
            "header_field": header_field,
            "data_field": data_field,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class CrossTabTool(BaseTool):
    tool_type = "CrossTab"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return crosstab_tool(inputs, config, context)
