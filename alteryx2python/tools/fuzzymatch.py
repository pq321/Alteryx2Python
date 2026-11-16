from __future__ import annotations

from collections import defaultdict
from itertools import combinations
import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _match_key(value, field):
    if pd.isna(value) or value == "":
        return None if field.get("ignore_empty", True) else ""
    text = str(value)
    mode = field.get("key_function") or "WholeField"
    if mode in {"Digits", "DigitsReverse"}:
        text = re.sub(r"[^0-9]", "", text)
        if mode == "DigitsReverse":
            text = text[::-1]
        length = field.get("max_key_length", 0)
        if length > 0:
            text = text[:length]
    return text.upper()


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

    record_id_field = str(config.get("record_id_field", ""))
    fields = config.get("match_fields", [])
    source_id = config.get("source_id_field") if config.get("merge_mode") else None
    if not record_id_field or not fields or config.get("merge_mode") and not source_id:
        raise ValueError("Fuzzy Match requires record IDs, matching fields and source IDs in merge mode")
    if any(config.get(option) for option in ("output_key", "output_unmatched", "output_make_group", "generate_keys")):
        raise NotImplementedError("Fuzzy Match generated-key, unmatched and group output modes need native calibration")
    for field in fields:
        mode = field.get("key_function") or "WholeField"
        algorithm = field.get("match_function") or "None"
        if field.get("preprocess") or algorithm != "None" or mode not in {"WholeField", "Digits", "DigitsReverse"}:
            raise NotImplementedError(f"Unsupported Fuzzy Match profile: {mode} / {algorithm}")
    names = [field["field_name"] for field in fields]
    required = [record_id_field, *names, *([source_id] if source_id else [])]
    ensure_fields_exist(input_frame, required)
    ids = input_frame[record_id_field]
    if ids.isna().any() or ids.duplicated().any():
        raise ValueError("Fuzzy Match requires unique non-null record IDs")
    source_ids = input_frame[source_id].tolist() if source_id else None
    groups = defaultdict(list)
    for index, values in enumerate(input_frame[names].itertuples(index=False, name=None)):
        key = tuple(_match_key(value, field) for value, field in zip(values, fields, strict=True))
        if None not in key:
            groups[key].append(index)
    pairs = []
    minimum = max(float(config.get("match_threshold", 0)), *(float(field.get("match_threshold", 0)) for field in fields))
    if minimum <= 100:
        for group in groups.values():
            for left, right in combinations(group, 2):
                if source_ids is None or source_ids[left] != source_ids[right]:
                    pairs.append(tuple(sorted((ids.iloc[left], ids.iloc[right]))))
    pairs.sort()
    output = pd.DataFrame({
        record_id_field: pd.Series([pair[0] for pair in pairs], dtype=ids.dtype),
        f"{record_id_field}2": pd.Series([pair[1] for pair in pairs], dtype=ids.dtype),
    })
    if config.get("output_score"):
        output["MatchScore"] = 100.0

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
