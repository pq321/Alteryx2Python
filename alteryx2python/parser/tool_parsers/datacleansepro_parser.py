from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def _bool_attribute(node: Any, default: bool = False) -> bool:
    raw = attributes(node).get("value")
    if raw is None:
        return default
    return str(raw).lower() == "true"


def _selected_fields(fields_node: Any) -> list[str]:
    fields = []
    for field in as_list(child(fields_node, "Field")):
        attrs = attributes(field)
        if str(attrs.get("selected", "False")).lower() == "true":
            fields.append(str(attrs.get("value", "")))
    return [field for field in fields if field]


def parse_datacleansepro_config(raw_config: dict[str, Any]) -> ToolParserResult:
    normalized = {
        "selected_fields": _selected_fields(child(raw_config, "Fields")),
        "remove_null_rows": _bool_attribute(child(raw_config, "RemoveNullRows")),
        "remove_null_columns": _bool_attribute(child(raw_config, "RemoveNullColumns")),
        "replace_string_nulls": _bool_attribute(child(raw_config, "Checkbox_ReplaceStringColumns"))
        and _bool_attribute(child(raw_config, "ReplaceWithBlanks")),
        "replace_numeric_nulls": _bool_attribute(child(raw_config, "Checkbox_ReplaceNumericColumns"))
        and _bool_attribute(child(raw_config, "ReplaceWithZero")),
        "remove_leading_trailing_whitespace": _bool_attribute(
            child(raw_config, "RemoveLeadingAndTrailingWhitespace")
        ),
        "remove_tabs_line_breaks_duplicate_whitespace": _bool_attribute(
            child(raw_config, "RemoveTabsLineBreaksAndDuplicates")
        ),
        "remove_all_whitespace": _bool_attribute(child(raw_config, "RemoveAllWhitespaces")),
        "remove_letters": _bool_attribute(child(raw_config, "RemoveLetters")),
        "remove_numbers": _bool_attribute(child(raw_config, "RemoveNumbers")),
        "remove_punctuation": _bool_attribute(child(raw_config, "RemovePunctuation")),
        "modify_case": _bool_attribute(child(raw_config, "CheckBox_ModifyCase")),
        "case_mode": str(attributes(child(raw_config, "ModifyCase")).get("value", "")),
    }
    return ToolParserResult(normalized_config=normalized)
