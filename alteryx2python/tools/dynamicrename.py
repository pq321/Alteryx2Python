from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def dynamicrename_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Targets" not in inputs:
        raise KeyError("DynamicRename tool requires a Targets anchor")
    input_frame = inputs["Targets"]
    rename_mode = str(config.get("rename_mode", "")).lower()
    selections = config.get("selected_fields", {"*Unknown": True})
    fields = [name for name in input_frame if selections.get(name, selections.get("*Unknown", False))]
    options = config.get("options", {})
    rename_map = _rename_fields(inputs, fields, rename_mode, config, options, context)
    names = [rename_map.get(field, field) for field in input_frame]
    if len(set(names)) != len(names):
        raise ValueError("DynamicRename produced duplicate output field names")

    output = input_frame.rename(columns=rename_map)
    if rename_mode == "firstrow":
        output = output.iloc[1:].reset_index(drop=True)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DynamicRename",
        source_tool_id=config.get("source_tool_id"),
        inputs=inputs,
        outputs=outputs,
        status="success",
        config={
            "rename_mode": rename_mode,
            "expression": config.get("expression", ""),
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


def _rename_fields(inputs, fields, mode, config, options, context):
    if mode == "formula":
        expression = parse_expression(config["expression"])
        return {name: evaluate_expression(expression, {"_CurrentField_": name}) for name in fields}
    if mode in {"add", "remove"}:
        return _affix_renames(fields, mode, options, context)
    if mode == "firstrow":
        frame = inputs["Targets"]
        return {} if frame.empty else _paired_renames(fields, frame.iloc[0][fields], options, context)
    if mode == "rightinputmetadata":
        if options.get("ChangeFields", "False").lower() == "true":
            raise NotImplementedError("DynamicRename metadata type changes are unsupported")
        return _paired_renames(fields, inputs["Source"].columns, options, context)
    if mode == "rightinputrows":
        source = inputs["Source"]
        names = source[options["NewName"]]
        if options.get("InputMode", "Positional").lower() == "mapped":
            mapping = dict(zip(source[options["OldName"]], names))
            return _paired_renames(fields, [mapping.get(name, name) for name in fields], options, context)
        return _paired_renames(fields, names, options, context)
    raise NotImplementedError(f"Unsupported DynamicRename mode: {mode}")


def _affix_renames(fields, mode, options, context):
    prefix = options.get("Type", "Prefix").lower() == "prefix"
    affix = options.get("Text", "")
    rename_map = {}
    for name in fields:
        if mode == "add":
            rename_map[name] = affix + name if prefix else name + affix
        elif (name.startswith(affix) if prefix else name.endswith(affix)):
            rename_map[name] = name.removeprefix(affix) if prefix else name.removesuffix(affix)
        else:
            _handle_rename_issue(options, context, f"Field {name!r} does not have {affix!r}")
    return rename_map


def _paired_renames(fields, names, options, context):
    if len(fields) != len(names):
        _handle_rename_issue(options, context, "DynamicRename name count differs from selected field count")
    rename_map = {}
    for old, new in zip(fields, names):
        if pd.isna(new) or not str(new):
            _handle_rename_issue(options, context, f"Missing new name for {old!r}")
        else:
            rename_map[old] = str(new)
    return rename_map


def _handle_rename_issue(options, context, message):
    policy = options.get("OnError", "Error").lower()
    if policy == "error":
        raise ValueError(message)
    if policy in {"warn", "warning"}:
        context.record_warning(message)


class DynamicRenameTool(BaseTool):
    tool_type = "DynamicRename"
    input_anchors = ("Targets", "Source")
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return dynamicrename_tool(inputs, config, context)
