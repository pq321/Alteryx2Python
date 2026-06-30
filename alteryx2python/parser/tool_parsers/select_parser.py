from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def parse_select_config(raw_config: dict[str, Any]) -> ToolParserResult:
    select_fields_node = child(raw_config, "SelectFields")
    select_fields = as_list(select_fields_node.get("SelectField", []))
    parsed_fields: list[dict[str, Any]] = []
    warnings: list[str] = []

    for field in select_fields:
        field_attrs = attributes(field)
        source = field_attrs.get("field", "")
        rename = field_attrs.get("rename", source)
        parsed_fields.append(
            {
                "source": source,
                "rename": rename,
                "selected": str(field_attrs.get("selected", "True")).lower() == "true",
                "dtype": field_attrs.get("type"),
                "forced": str(field_attrs.get("forced", "False")).lower() == "true",
                "size": field_attrs.get("size"),
            }
        )

    if not parsed_fields:
        warnings.append("Select config contains no SelectField entries")

    return ToolParserResult(
        normalized_config={"select_fields": parsed_fields},
        warnings=warnings,
    )
