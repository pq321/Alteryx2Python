from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def _bool_value(node: Any, default: bool = False) -> bool:
    raw = attributes(node).get("value")
    if raw is None:
        return default
    return str(raw).strip().lower() == "true"


def parse_findreplace_config(raw_config: dict[str, Any]) -> ToolParserResult:
    append_fields = [
        str(attributes(field).get("field", ""))
        for field in as_list(child(raw_config, "ReplaceAppendFields").get("Field", []))
        if attributes(field).get("field")
    ]
    return ToolParserResult(
        normalized_config={
            "field_find": text(raw_config.get("FieldFind")),
            "field_search": text(raw_config.get("FieldSearch")),
            "replace_found_field": text(raw_config.get("ReplaceFoundField")),
            "find_mode": text(raw_config.get("FindMode"), "FindAny"),
            "no_case": _bool_value(raw_config.get("NoCase")),
            "match_whole_word": _bool_value(raw_config.get("MatchWholeWord")),
            "replace_mode": text(raw_config.get("ReplaceMode"), "Replace"),
            "replace_multiple_found": _bool_value(raw_config.get("ReplaceMultipleFound"), default=True),
            "append_fields": append_fields,
        }
    )
