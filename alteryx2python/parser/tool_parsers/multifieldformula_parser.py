from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def _bool_value(node: Any, default: bool = False) -> bool:
    raw = attributes(node).get("value")
    if raw is None:
        return default
    return str(raw).strip().lower() == "true"


def parse_multifieldformula_config(raw_config: dict[str, Any]) -> ToolParserResult:
    fields = [
        str(attributes(field).get("name", ""))
        for field in as_list(child(raw_config, "Fields").get("Field", []))
        if attributes(field).get("name") and str(attributes(field).get("selected", "True")).lower() != "false"
    ]
    output_type = attributes(raw_config.get("OutputFieldType", {}))
    return ToolParserResult(
        normalized_config={
            "field_type": text(raw_config.get("FieldType"), ""),
            "fields": fields,
            "copy_output": _bool_value(raw_config.get("CopyOutput")),
            "new_field_add_on": text(raw_config.get("NewFieldAddOn"), ""),
            "new_field_add_on_pos": text(raw_config.get("NewFieldAddOnPos"), "Suffix"),
            "expression": text(raw_config.get("Expression"), ""),
            "change_field_type": _bool_value(raw_config.get("ChangeFieldType")),
            "output_field_type": dict(output_type),
        }
    )
