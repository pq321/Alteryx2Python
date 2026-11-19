from __future__ import annotations

import re
import warnings
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


NATIVE_METHODS = {
    "Sum": "sum", "Avg": "avg", "XRow": "percent_row", "XCol": "percent_column",
    "Count": "countnonnull", "First": "first", "Last": "last", "Concat": "concat",
    "TotCol": "total_column", "TotRow": "total_row",
}


def crosstab_methods(methods):
    unsupported = set(methods) - NATIVE_METHODS.keys()
    if unsupported:
        raise NotImplementedError(f"CrossTab aggregation is unsupported: {', '.join(sorted(unsupported))}")
    if set(methods) == {"TotRow"}:
        raise ValueError("CrossTab Total Row requires another output method")
    return [(name, method) for name, method in NATIVE_METHODS.items() if name in methods]


def _cross_aggregate(values, method, separator=','):
    if method == 'first':
        return values[0]
    if method == 'last':
        return values[-1]
    if method == 'count':
        return len(values)
    if method == 'countnonnull':
        return float(sum(not pd.isna(value) for value in values))
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


def _pivot_sum(values):
    return float(pd.to_numeric(pd.Series(values), errors="coerce").sum())


def pivot_crosstab(frame, groups, header, data, methods, separator, field_size):
    single_method = len(methods) == 1
    total_column = ("TotCol", "total_column") in methods
    total_row = ("TotRow", "total_row") in methods
    methods = [(label, method) for label, method in methods if method not in {"total_row", "total_column"}]
    percent_row = ("XRow", "percent_row") in methods
    percent_column = ("XCol", "percent_column") in methods
    names = {}
    for value in frame[header].dropna().astype(str):
        names.setdefault(value.casefold(), value)
    columns = {}
    used = {field.casefold() for field in groups}
    if total_column:
        used.add("total")
    for key, value in sorted(names.items()):
        field = re.sub(r"[^\w]", "_", value)
        for label, method in methods:
            unprefixed = single_method and method in {"sum", "first", "last"}
            stem = field if unprefixed else f"{label}_{field}"
            name = stem
            suffix = 2
            while name.casefold() in used:
                name = f"{stem}_{suffix}"
                suffix += 1
            columns[key, method] = name
            used.add(name.casefold())

    if groups:
        ordered = frame.sort_values(groups, kind="stable", na_position="first")
        batches = ordered.groupby(groups, sort=False, dropna=False)
    else:
        batches = [((), frame)] if not frame.empty else []
    cells = []
    all_values = {}
    for _, batch in batches:
        row = {field: batch.iloc[0][field] for field in groups}
        values = {}
        for source_header, value in zip(batch[header], batch[data]):
            if not pd.isna(source_header):
                values.setdefault(str(source_header).casefold(), []).append(value)
        cells.append((row, values))
        if total_row or percent_column:
            for key, items in values.items():
                all_values.setdefault(key, []).extend(items)
    if total_row and cells:
        cells.append((dict.fromkeys(groups), all_values))
    column_sums = {key: _pivot_sum(items) for key, items in all_values.items()} if percent_column else {}
    rows = []
    truncated = False
    for row, values in cells:
        sums = {key: _pivot_sum(items) for key, items in values.items()} if total_column or percent_row or percent_column else {}
        total = sum(sums.values())
        for (key, method), column in columns.items():
            if key not in values:
                cell = None
            elif method == "percent_row":
                cell = 100 * sums[key] / total if total else None
            elif method == "percent_column":
                denominator = column_sums[key]
                cell = 100 * sums[key] / denominator if denominator else None
            else:
                cell = _cross_aggregate(values[key], method, separator)
            if method == "concat" and field_size is not None and cell is not None and len(cell) > field_size:
                cell = cell[:field_size]
                truncated = True
            row[column] = cell
        if total_column:
            row["Total"] = total
        rows.append(row)
    if truncated:
        warnings.warn("CrossTab concatenation exceeded Field Size and was truncated", RuntimeWarning, stacklevel=2)
    headers = [*groups, *columns.values(), *(["Total"] if total_column else [])]
    output = pd.DataFrame(rows, columns=headers, dtype=object)
    return output.where(pd.notna(output), None)


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
    if not header_field or not data_field:
        raise ValueError("CrossTab config requires header_field and data_field")
    ensure_fields_exist(input_frame, [*group_fields, header_field, data_field])

    methods = config.get("methods")
    if methods:
        output = pivot_crosstab(
            input_frame, group_fields, header_field, data_field, crosstab_methods(methods),
            config.get("separator", ","), config.get("field_size"),
        )
    else:
        output = _legacy_pivot(input_frame, group_fields, header_field, data_field, method, config.get("separator", ","))
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


def _legacy_pivot(input_frame, group_fields, header_field, data_field, method, separator):
    method = method.lower()
    if method not in {'first', 'last', 'count', 'sum', 'avg', 'average', 'min', 'max', 'median', 'concat', 'concatenate'}:
        raise NotImplementedError(f'CrossTab aggregation is unsupported: {method}')
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
            output_row[header] = _cross_aggregate(values, method, separator) if values else None
        output_rows.append(output_row)
    output = pd.DataFrame(output_rows, columns=[*group_fields, *header_values])
    return output.astype(object).where(pd.notna(output), None)


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
