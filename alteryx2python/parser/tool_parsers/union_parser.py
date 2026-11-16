from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_union_config(raw_config: dict[str, Any]) -> ToolParserResult:
    normalized = {
        "mode": text(raw_config.get("Mode"), "Unknown"),
        "by_name_error_mode": text(raw_config.get("ByName_ErrorMode"), ""),
        "by_name_output_mode": text(raw_config.get("ByName_OutputMode"), ""),
        "set_output_order": str(attributes(raw_config.get("SetOutputOrder", {})).get("value", "False")).lower() == "true",
        "output_order": [text(connection, "") for connection in as_list(child(raw_config, "OutputOrder").get("Connection", []))],
    }
    manual_inputs = {}
    for meta in as_list(child(raw_config, "MultiMetaInfo").get("MetaInfo", [])):
        name = attributes(meta).get("name")
        if not name:
            continue
        manual_inputs[name] = [
            {"name": field["name"], "column": int(field["column"])}
            for element in as_list(child(meta, "RecordInfo").get("Field", []))
            if (field := attributes(element)).get("name") and field.get("column")
        ]
    if manual_inputs:
        normalized["manual_inputs"] = manual_inputs
    return ToolParserResult(normalized_config=normalized)
