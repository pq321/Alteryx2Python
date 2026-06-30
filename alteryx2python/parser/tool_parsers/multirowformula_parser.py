from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def _bool_attribute(node: Any, default: bool = False) -> bool:
    raw = attributes(node).get("value")
    if raw is None:
        return default
    return str(raw).lower() == "true"


def _int_attribute(node: Any, default: int = 1) -> int:
    raw = attributes(node).get("value")
    if raw is None or str(raw).strip() == "":
        return default
    return int(raw)


def _group_by_fields(node: Any) -> list[str]:
    fields: list[str] = []
    for field in as_list(child(node, "Field")):
        value = attributes(field).get("field")
        if value:
            fields.append(str(value))
    return fields


def parse_multirowformula_config(raw_config: dict[str, Any]) -> ToolParserResult:
    normalized = {
        "update_field": _bool_attribute(child(raw_config, "UpdateField")),
        "update_field_name": text(child(raw_config, "UpdateField_Name")),
        "create_field_name": text(child(raw_config, "CreateField_Name")),
        "create_field_type": text(child(raw_config, "CreateField_Type")),
        "create_field_size": text(child(raw_config, "CreateField_Size")),
        "other_rows": text(child(raw_config, "OtherRows"), "Empty"),
        "num_rows": _int_attribute(child(raw_config, "NumRows"), default=1),
        "expression": text(child(raw_config, "Expression")),
        "group_by_fields": _group_by_fields(child(raw_config, "GroupByFields")),
    }
    return ToolParserResult(normalized_config=normalized)
