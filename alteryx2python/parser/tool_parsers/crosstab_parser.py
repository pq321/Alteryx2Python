from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def parse_crosstab_config(raw_config: dict[str, Any]) -> ToolParserResult:
    group_fields_node = child(raw_config, "GroupFields")
    methods_node = child(raw_config, "Methods")
    normalized = {
        "group_fields": [
            attributes(field).get("field", "")
            for field in as_list(group_fields_node.get("Field", []))
        ],
        "header_field": attributes(child(raw_config, "HeaderField")).get("field", ""),
        "data_field": attributes(child(raw_config, "DataField")).get("field", ""),
        "method": attributes(child(methods_node, "Method")).get("method", "First"),
    }
    return ToolParserResult(normalized_config=normalized)
