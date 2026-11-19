from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_crosstab_config(raw_config: dict[str, Any]) -> ToolParserResult:
    group_fields_node = child(raw_config, "GroupFields")
    methods_node = child(raw_config, "Methods")
    methods = [str(attributes(method).get("method", "")) for method in as_list(methods_node.get("Method", []))]
    normalized = {
        "group_fields": [
            attributes(field).get("field", "")
            for field in as_list(group_fields_node.get("Field", []))
        ],
        "header_field": attributes(child(raw_config, "HeaderField")).get("field", ""),
        "data_field": attributes(child(raw_config, "DataField")).get("field", ""),
        "method": methods[0] if methods else "First",
    }
    if methods:
        normalized["methods"] = methods
    if "Separator" in methods_node:
        normalized["separator"] = text(methods_node["Separator"], "").replace(r"\s", " ").replace(r"\t", "\t").replace(r"\n", "\n")
    size = attributes(child(methods_node, "FieldSize")).get("value")
    if size not in (None, ""):
        normalized["field_size"] = int(size)
    return ToolParserResult(normalized_config=normalized)
