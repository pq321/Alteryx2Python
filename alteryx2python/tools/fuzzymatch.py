from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def fuzzymatch_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("FuzzyMatch tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    output = input_frame.copy()
    record_id_field = str(config.get("record_id_field", ""))
    if record_id_field and record_id_field in output.columns and "FuzzyMatchGroupID" not in output.columns:
        output["FuzzyMatchGroupID"] = output[record_id_field]
    if config.get("output_score") and "FuzzyMatchScore" not in output.columns:
        output["FuzzyMatchScore"] = 100.0
    if config.get("output_key") and "FuzzyMatchKey" not in output.columns:
        fields = [
            field.get("field_name", "")
            for field in config.get("match_fields", [])
            if isinstance(field, dict) and field.get("field_name")
        ]
        output["FuzzyMatchKey"] = output[fields].astype(str).agg("|".join, axis=1) if fields else ""

    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="FuzzyMatch",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "record_id_field": record_id_field,
            "match_threshold": config.get("match_threshold", 0.0),
            "match_fields": config.get("match_fields", []),
            "baseline_semantics": "passthrough_with_optional_metadata_columns",
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class FuzzyMatchTool(BaseTool):
    tool_type = "FuzzyMatch"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return fuzzymatch_tool(inputs, config, context)
