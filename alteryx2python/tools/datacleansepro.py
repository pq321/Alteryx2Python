from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.datacleansing import (
    _all_selected_values_empty,
    _clean_series,
    _empty_selected_columns,
    _input_frame,
    _recorded_options,
    _selected_fields,
)


def datacleansepro_tool(
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

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="DataCleansePro",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
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


class DataCleanseProTool(BaseTool):
    tool_type = "DataCleansePro"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return datacleansepro_tool(inputs, config, context)
