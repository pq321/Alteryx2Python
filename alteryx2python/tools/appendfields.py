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

    target_rows = targets.to_dict("records")
    source_rows = source.to_dict("records")
    rows = []
    for target in target_rows:
        for source_row in source_rows:
            row = dict(target)
            for column, value in source_row.items():
                output_column = column if column not in row else f"Source_{column}"
                row[output_column] = value
            rows.append(row)
    columns = [*targets.columns, *(column if column not in targets.columns else f'Source_{column}' for column in source.columns)]
    output = pd.DataFrame(rows, columns=columns)
    fields = config.get('select_fields', [])
    if fields:
        selected, explicit = {}, set()
        for field in fields:
            name = str(field['source'])
            if name == '*Unknown':
                continue
            if name.startswith('Target_'):
                name = name[len('Target_'):]
            elif name.startswith('Source_') and name[len('Source_'):] not in targets.columns:
                name = name[len('Source_'):]
            explicit.add(name)
            if field.get('selected', True):
                selected[field.get('rename') or name] = coerce_field(output[name], field.get('dtype'), field.get('size'))
        if any(field['source'] == '*Unknown' and field.get('selected', True) for field in fields):
            selected.update({column: output[column] for column in output.columns if column not in explicit and column not in selected})
        output = pd.DataFrame(selected, index=output.index)
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
