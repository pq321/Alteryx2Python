from __future__ import annotations

import re
import string
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


PUNCTUATION_TRANSLATION = str.maketrans("", "", string.punctuation)


def datacleansing_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = _input_frame(inputs)
    output = input_frame.copy()
    selected_fields = _selected_fields(output, config)

    if config.get("remove_null_rows"):
        output = output.loc[~_all_selected_values_empty(output, selected_fields)].copy()
    if config.get("remove_null_columns"):
        output = output.drop(columns=_empty_selected_columns(output, selected_fields))
        selected_fields = [field for field in selected_fields if field in output.columns]

    for field in selected_fields:
        output[field] = _clean_series(output[field], config)

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


def _clean_series(series: pd.Series, config: dict[str, Any]) -> pd.Series:
    cleaned = series.copy()
    if config.get("replace_string_nulls"):
        cleaned = cleaned.fillna("")
    if config.get("replace_numeric_nulls"):
        cleaned = cleaned.fillna(0)

    if _uses_text_operations(config):
        cleaned = cleaned.map(lambda value: _clean_text_value(value, config))
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


def _clean_text_value(value: Any, config: dict[str, Any]) -> Any:
    if pd.isna(value):
        return value
    text = str(value)
    if config.get("remove_leading_trailing_whitespace"):
        text = text.strip()
    if config.get("remove_tabs_line_breaks_duplicate_whitespace"):
        text = re.sub(r"\s+", " ", text)
    if config.get("remove_all_whitespace"):
        text = re.sub(r"\s+", "", text)
    if config.get("remove_letters"):
        text = re.sub(r"[A-Za-z]", "", text)
    if config.get("remove_numbers"):
        text = re.sub(r"\d", "", text)
    if config.get("remove_punctuation"):
        text = text.translate(PUNCTUATION_TRANSLATION)
    if config.get("modify_case"):
        text = _modify_case(text, str(config.get("case_mode", "")))
    return text


def _modify_case(value: str, case_mode: str) -> str:
    if case_mode == "upper":
        return value.upper()
    if case_mode == "lower":
        return value.lower()
    if case_mode == "title":
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
