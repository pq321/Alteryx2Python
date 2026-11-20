from __future__ import annotations

from decimal import Decimal
import re
import string
from typing import Any
from unicodedata import category

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.field_contracts import INTEGER_BYTES, STRING_TYPES


PUNCTUATION_TRANSLATION = str.maketrans("", "", string.punctuation)


def datacleansing_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    output = input_frame.copy()

    if config.get("remove_null_rows"):
        output = output.dropna(axis="index", how="all")
    if config.get("remove_null_columns"):
        output = output.dropna(axis="columns", how="all")

    configured = config.get("selected_fields")
    selected_fields = list(output.columns) if configured is None else [
        field for field in configured if field in output.columns
    ]
    schema = output.attrs.get("alteryx_schema", [])
    field_types = {field["name"]: field.get("type") for field in schema}
    for field in selected_fields:
        output[field] = _clean_series(output[field], config, classic=True, field_type=field_types.get(field))
    if schema:
        output.attrs["alteryx_schema"] = [field for field in schema if field["name"] in output.columns]

    outputs = {"Output26": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DataCleansing",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input2": input_frame},
        outputs=outputs,
        status="success",
        config={
            "selected_fields": selected_fields,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
            "options": _recorded_options(config),
        },
    )
    return outputs


def _input_frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Input2" in inputs:
        return inputs["Input2"]
    if "Input" in inputs:
        return inputs["Input"]
    raise KeyError("DataCleansing tool requires an Input2 anchor")


def _selected_fields(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    configured = [str(field) for field in config.get("selected_fields", [])]
    return [field for field in configured if field in frame.columns] or list(frame.columns)


def _all_selected_values_empty(frame: pd.DataFrame, selected_fields: list[str]) -> pd.Series:
    if not selected_fields:
        return pd.Series(False, index=frame.index)
    return frame[selected_fields].apply(lambda row: all(_is_empty(value) for value in row), axis=1)


def _empty_selected_columns(frame: pd.DataFrame, selected_fields: list[str]) -> list[str]:
    return [
        field
        for field in selected_fields
        if frame[field].map(_is_empty).all()
    ]


def _is_empty(value: Any) -> bool:
    return pd.isna(value) or value == ""


def _clean_series(series: pd.Series, config: dict[str, Any], *, classic=False, field_type=None) -> pd.Series:
    cleaned = series.copy()
    numeric = pd.api.types.is_numeric_dtype(series)
    textual = isinstance(series.dtype, pd.StringDtype) or pd.api.types.infer_dtype(series, skipna=True) in {"string", "empty"}
    if classic:
        if field_type:
            numeric = field_type in INTEGER_BYTES or field_type in {"Float", "Double", "FixedDecimal"}
            textual = field_type in STRING_TYPES
        else:
            inferred = pd.api.types.infer_dtype(series, skipna=True)
            numeric = (numeric and not pd.api.types.is_bool_dtype(series)) or inferred in {
                "integer", "floating", "mixed-integer-float", "decimal",
            }
            textual = textual and not numeric
    if config.get("replace_string_nulls") and textual:
        cleaned = cleaned.fillna("")
    if config.get("replace_numeric_nulls") and numeric:
        cleaned = cleaned.fillna(Decimal(0) if field_type == "FixedDecimal" else 0)

    # Native DataCleansing text options (whitespace, case, strip letters or
    # digits) only apply to string fields; numeric columns pass through.
    if _uses_text_operations(config) and textual:
        cleaned = cleaned.map(lambda value: _clean_text_value(value, config, classic=classic))
    return cleaned


def _uses_text_operations(config: dict[str, Any]) -> bool:
    return any(
        config.get(option)
        for option in (
            "remove_leading_trailing_whitespace",
            "remove_tabs_line_breaks_duplicate_whitespace",
            "remove_all_whitespace",
            "remove_letters",
            "remove_numbers",
            "remove_punctuation",
            "modify_case",
        )
    )


def _clean_text_value(value: Any, config: dict[str, Any], *, classic=False) -> Any:
    if pd.isna(value):
        return value
    text = str(value)
    if config.get("remove_tabs_line_breaks_duplicate_whitespace"):
        text = re.sub(r"\s+", " ", text)
    if config.get("remove_all_whitespace"):
        text = re.sub(r"\s+", "", text)
    if config.get("remove_letters"):
        text = "".join(char for char in text if not char.isalpha())
    if config.get("remove_numbers"):
        text = re.sub(r"[0-9０-９]", "", text)
    if config.get("remove_punctuation"):
        text = text.translate(PUNCTUATION_TRANSLATION)
        if classic:
            text = "".join(char for char in text if not _is_classic_punctuation(char))
    if config.get("remove_leading_trailing_whitespace"):
        text = text.strip(" \t\n\r\u00a0")
    if config.get("modify_case"):
        text = _modify_case(text, str(config.get("case_mode", "")), classic=classic)
    return text


def _is_classic_punctuation(char):
    return category(char).startswith("P") or (
        "\uff01" <= char <= "\uff0f" or "\uff1a" <= char <= "\uff20"
        or "\uff3b" <= char <= "\uff40" or "\uff5b" <= char <= "\uff5e"
        or "\u2200" <= char <= "\u22ff"
    )


def _modify_case(value: str, case_mode: str, *, classic=False) -> str:
    if case_mode == "upper":
        return value.upper()
    if case_mode == "lower":
        return value.lower()
    if case_mode == "title":
        if classic:
            return re.sub(
                r"[^\W_]+(?:['-][^\W_]+)*",
                lambda word: word[0][0].upper() + word[0][1:].lower(),
                value,
            )
        return value.title()
    return value


def _recorded_options(config: dict[str, Any]) -> dict[str, Any]:
    return {
        key: config.get(key)
        for key in (
            "remove_null_rows",
            "remove_null_columns",
            "replace_string_nulls",
            "replace_numeric_nulls",
            "remove_leading_trailing_whitespace",
            "remove_tabs_line_breaks_duplicate_whitespace",
            "remove_all_whitespace",
            "remove_letters",
            "remove_numbers",
            "remove_punctuation",
            "modify_case",
            "case_mode",
        )
    }


class DataCleansingTool(BaseTool):
    tool_type = "DataCleansing"
    input_anchors = ("Input2",)
    output_anchors = ("Output26",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return datacleansing_tool(inputs, config, context)
