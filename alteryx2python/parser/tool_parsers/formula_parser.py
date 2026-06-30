from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def parse_formula_config(raw_config: dict[str, Any]) -> ToolParserResult:
    formula_fields_node = child(raw_config, "FormulaFields")
    formula_fields = as_list(formula_fields_node.get("FormulaField", []))
    parsed_fields = []
    for field in formula_fields:
        field_attrs = attributes(field)
        parsed_fields.append(
            {
                "field": field_attrs.get("field", ""),
                "expression": field_attrs.get("expression", ""),
                "type": field_attrs.get("type"),
                "size": field_attrs.get("size"),
                "enabled": str(field_attrs.get("enabled", "true")).lower() == "true",
            }
        )
    return ToolParserResult(normalized_config={"formula_fields": parsed_fields})
