from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_transpose_config(raw_config: dict[str, Any]) -> ToolParserResult:
    key_fields_node = child(raw_config, "KeyFields")
    data_fields_node = child(raw_config, "DataFields")
    normalized = {
        "error_warn": text(raw_config.get("ErrorWarn"), ""),
        "key_fields": [attributes(field).get("field", "") for field in as_list(key_fields_node.get("Field", []))],
        "data_fields": [
            {
                "field": attributes(field).get("field", ""),
                "selected": str(attributes(field).get("selected", "False")).lower() == "true",
            }
            for field in as_list(data_fields_node.get("Field", []))
        ],
    }
    return ToolParserResult(normalized_config=normalized)
