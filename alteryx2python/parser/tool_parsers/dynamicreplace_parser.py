from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def parse_dynamicreplace_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "field_field_name": text(child(raw_config, "Field_FieldName"), ""),
            "field_output_value": text(child(raw_config, "Field_OutputValue"), ""),
            "field_expression": text(child(raw_config, "Field_Expression"), ""),
            "value_is_expression": str(attributes(child(raw_config, "ValueIsExpression")).get("value", "False")).lower()
            == "true",
            "unmatched_behavior": text(child(raw_config, "Unmatched_Behavior"), ""),
            "field_type_mode": text(child(raw_config, "FieldTypeMode"), ""),
            "output_field_type": attributes(child(raw_config, "OutputFieldType")),
        }
    )
