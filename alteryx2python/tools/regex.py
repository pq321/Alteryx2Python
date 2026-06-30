from __future__ import annotations

import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _replacement(template: str, match: re.Match[str]) -> str:
    result = template
    for index, value in enumerate(match.groups(), start=1):
        result = result.replace(f"${index}", "" if value is None else value)
    return result


def _regex_flags(config: dict[str, Any]) -> int:
    return re.IGNORECASE if config.get("case_insensitive", True) else 0


def _parse_simple(value: Any, pattern: re.Pattern[str], config: dict[str, Any]) -> list[str]:
    text = "" if pd.isna(value) else str(value)
    matches = pattern.findall(text)
    values = [item if isinstance(item, str) else item[0] for item in matches]
    return values[: int(config.get("parse_simple", {}).get("num_fields", 1))]


def regex_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("RegEx tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    field = str(config.get("field", ""))
    ensure_fields_exist(input_frame, [field])
    pattern = re.compile(str(config.get("regex_expression", "")), flags=_regex_flags(config))
    method = str(config.get("method", "Match"))

    output = input_frame.copy()
    if method == "Match":
        match_field = str(config.get("match_field", f"{field}_Matched"))
        output[match_field] = [pattern.search("" if pd.isna(value) else str(value)) is not None for value in output[field]]
    elif method == "Replace":
        template = str(config.get("replace_expression", ""))
        copy_unmatched = bool(config.get("copy_unmatched", True))
        values = []
        for value in output[field]:
            text = "" if pd.isna(value) else str(value)
            match = pattern.search(text)
            if match is None:
                values.append(text if copy_unmatched else "")
            else:
                values.append(_replacement(template, match))
        output[field] = values
    elif method == "ParseComplex":
        fields = [str(item) for item in config.get("parse_complex_fields", [])]
        for field_name in fields:
            output[field_name] = ""
        for index, value in output[field].items():
            match = pattern.search("" if pd.isna(value) else str(value))
            if match is None:
                continue
            for field_name, group in zip(fields, match.groups()):
                output.at[index, field_name] = "" if group is None else group
    elif method == "ParseSimple":
        settings = config.get("parse_simple", {})
        root_name = str(settings.get("root_name", field))
        num_fields = int(settings.get("num_fields", 1))
        names = [f"{root_name}{index}" for index in range(1, num_fields + 1)]
        for name in names:
            output[name] = ""
        for index, value in output[field].items():
            parts = _parse_simple(value, pattern, config)
            for name, part in zip(names, parts):
                output.at[index, name] = part
    else:
        raise NotImplementedError(f"RegEx method is not supported: {method}")

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="RegEx",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "field": field,
            "method": method,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class RegExTool(BaseTool):
    tool_type = "RegEx"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return regex_tool(inputs, config, context)
