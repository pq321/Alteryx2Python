from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input" not in inputs:
        raise KeyError("DynamicSelect tool requires an Input anchor")
    frame = inputs["Input"]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return frame


def _alteryx_type(series: pd.Series) -> str:
    dtype = series.dtype
    if pd.api.types.is_bool_dtype(dtype):
        return "Bool"
    if pd.api.types.is_integer_dtype(dtype):
        return "Int64"
    if pd.api.types.is_float_dtype(dtype):
        return "Double"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "DateTime"
    if pd.api.types.is_string_dtype(dtype):
        return "V_String"
    return "V_String"


def _schema_row(frame: pd.DataFrame, column: str, field_number: int) -> dict[str, Any]:
    alteryx_type = _alteryx_type(frame[column])
    return {
        "Name": column,
        "Type": alteryx_type,
        "FieldNumber": field_number,
        "Size": None,
        "Scale": None,
        "IsString": alteryx_type in {"String", "V_String", "V_WString", "WString"},
        "IsNumeric": alteryx_type in {"Byte", "Int16", "Int32", "Int64", "FixedDecimal", "Float", "Double"},
        "IsDateTime": alteryx_type in {"Date", "DateTime", "Time"},
        "IsStringOrDate": alteryx_type in {"String", "V_String", "V_WString", "WString", "Date", "DateTime", "Time"},
    }


def _is_selected(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    return str(value).strip().lower() == "true"


def _select_by_field_types(frame: pd.DataFrame, field_types: list[str]) -> list[str]:
    selected_types = {field_type.lower() for field_type in field_types}
    selected: list[str] = []
    for field_number, column in enumerate(frame.columns, start=1):
        row = _schema_row(frame, column, field_number)
        if str(row["Type"]).lower() in selected_types:
            selected.append(column)
    return selected


def _select_by_formula(frame: pd.DataFrame, expression: str) -> list[str]:
    parsed = parse_expression(expression.replace("&&", " AND ").replace("||", " OR "))
    selected: list[str] = []
    for field_number, column in enumerate(frame.columns, start=1):
        row = _schema_row(frame, column, field_number)
        if _is_selected(evaluate_expression(parsed, row)):
            selected.append(column)
    return selected


def dynamicselect_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    mode = str(config.get("mode", ""))
    if mode == "FieldTypes":
        selected_columns = _select_by_field_types(input_frame, [str(item) for item in config.get("field_types", [])])
    elif mode == "Formula":
        selected_columns = _select_by_formula(input_frame, str(config.get("expression", "")))
    else:
        raise NotImplementedError(f"DynamicSelect mode is not supported: {mode}")

    output = input_frame.loc[:, selected_columns].copy()
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DynamicSelect",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "mode": mode,
            "selected_columns": selected_columns,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DynamicSelectTool(BaseTool):
    tool_type = "DynamicSelect"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return dynamicselect_tool(inputs, config, context)
