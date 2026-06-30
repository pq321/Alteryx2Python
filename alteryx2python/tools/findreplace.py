from __future__ import annotations

import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _input_frame(inputs: dict[str, pd.DataFrame], anchor: str) -> pd.DataFrame:
    if anchor not in inputs:
        raise KeyError(f"FindReplace tool requires a {anchor} anchor")
    frame = inputs[anchor]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{anchor} anchor must contain a pandas DataFrame")
    return frame


def _match_span(value: Any, search: Any, config: dict[str, Any]) -> tuple[int, int] | None:
    text = "" if pd.isna(value) else str(value)
    needle = "" if pd.isna(search) else str(search)
    if needle == "":
        return None

    flags = re.IGNORECASE if config.get("no_case") else 0
    escaped = re.escape(needle)
    if config.get("match_whole_word"):
        pattern = rf"(?<!\w){escaped}(?!\w)"
    elif config.get("find_mode") == "FindBegin":
        pattern = rf"^{escaped}"
    elif config.get("find_mode") == "FindEnd":
        pattern = rf"{escaped}$"
    elif config.get("find_mode") in {"FindWhole", "FindEntire"}:
        pattern = rf"^{escaped}$"
    else:
        pattern = escaped
    match = re.search(pattern, text, flags=flags)
    if match is None:
        return None
    return match.span()


def _replace_text(value: Any, span: tuple[int, int], replacement: Any) -> str:
    text = "" if pd.isna(value) else str(value)
    replace_text = "" if pd.isna(replacement) else str(replacement)
    start, end = span
    return f"{text[:start]}{replace_text}{text[end:]}"


def _source_matches(value: Any, source: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    field_search = str(config.get("field_search", ""))
    ensure_fields_exist(source, [field_search])
    matches: list[dict[str, Any]] = []
    for row in source.to_dict("records"):
        span = _match_span(value, row[field_search], config)
        if span is not None:
            matches.append({**row, "_span": span})
            if not config.get("replace_multiple_found", True):
                break
    return matches


def findreplace_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    targets = _input_frame(inputs, "Targets")
    source = _input_frame(inputs, "Source")
    field_find = str(config.get("field_find", ""))
    replace_mode = str(config.get("replace_mode", "Replace"))
    ensure_fields_exist(targets, [field_find])

    output = targets.copy()
    matched_rows = []
    if replace_mode == "Append":
        append_fields = list(config.get("append_fields", [])) or [
            field for field in source.columns if field != config.get("field_search")
        ]
        ensure_fields_exist(source, append_fields)
        for field in append_fields:
            if field not in output.columns:
                output[field] = None
        for index, value in output[field_find].items():
            matches = _source_matches(value, source, config)
            if not matches:
                continue
            matched_rows.append(index)
            for match in matches:
                for field in append_fields:
                    output.at[index, field] = match[field]
    elif replace_mode == "Replace":
        replace_field = str(config.get("replace_found_field", ""))
        ensure_fields_exist(source, [replace_field])
        for index, value in output[field_find].items():
            current = value
            matches = _source_matches(current, source, config)
            if not matches:
                continue
            matched_rows.append(index)
            for match in matches:
                span = _match_span(current, match[str(config.get("field_search", ""))], config)
                if span is None:
                    continue
                current = _replace_text(current, span, match[replace_field])
            output.at[index, field_find] = current
    else:
        raise NotImplementedError(f"FindReplace replace_mode is not supported: {replace_mode}")

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="FindReplace",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Targets": targets, "Source": source},
        outputs=outputs,
        status="success",
        config={
            "field_find": field_find,
            "field_search": config.get("field_search"),
            "replace_mode": replace_mode,
            "matched_row_count": len(set(matched_rows)),
            "input_schema": {"Targets": snapshot_schema(targets), "Source": snapshot_schema(source)},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class FindReplaceTool(BaseTool):
    tool_type = "FindReplace"
    input_anchors = ("Targets", "Source")
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return findreplace_tool(inputs, config, context)
