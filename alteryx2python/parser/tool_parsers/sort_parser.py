from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def parse_sort_config(raw_config: dict[str, Any]) -> ToolParserResult:
    sort_info = child(raw_config, "SortInfo")
    field_nodes = as_list(sort_info.get("Field", [])) if isinstance(sort_info, dict) else []
    sort_fields: list[dict[str, str]] = []
    warnings: list[str] = []

    for field in field_nodes:
        field_attrs = attributes(field)
        name = str(field_attrs.get("field", ""))
        order = str(field_attrs.get("order", "Ascending"))
        if name:
            sort_fields.append({"field": name, "order": order})

    if not sort_fields:
        warnings.append("Sort config contains no fields")

    return ToolParserResult(normalized_config={"sort_fields": sort_fields}, warnings=warnings)
