from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, text


VALUE_MAP = {
    "Check Box (135)": "remove_null_rows",
    "Check Box (136)": "remove_null_columns",
    "Check Box (84)": "replace_string_nulls",
    "Check Box (117)": "replace_numeric_nulls",
    "Check Box (15)": "remove_leading_trailing_whitespace",
    "Check Box (109)": "remove_tabs_line_breaks_duplicate_whitespace",
    "Check Box (122)": "remove_all_whitespace",
    "Check Box (53)": "remove_letters",
    "Check Box (58)": "remove_numbers",
    "Check Box (70)": "remove_punctuation",
    "Check Box (77)": "modify_case",
}


def parse_datacleansing_config(config: dict[str, Any]) -> ToolParserResult:
    values = {
        str(attributes(entry).get("name", "")): text(entry)
        for entry in as_list(config.get("Value"))
        if isinstance(entry, dict)
    }
    normalized: dict[str, Any] = {
        "selected_fields": _parse_selected_fields(values.get("List Box (11)", "")),
        "case_mode": values.get("Drop Down (81)", ""),
    }
    for raw_name, normalized_name in VALUE_MAP.items():
        normalized[normalized_name] = _parse_bool(values.get(raw_name, "False"))
    return ToolParserResult(normalized_config=normalized)


def _parse_selected_fields(raw: str) -> list[str]:
    if not raw:
        return []
    return [field for row in csv.reader(StringIO(raw)) for field in row]


def _parse_bool(raw: str) -> bool:
    return str(raw).strip().lower() == "true"
