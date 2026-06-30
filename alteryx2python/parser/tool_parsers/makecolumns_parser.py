from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_makecolumns_config(raw_config: dict[str, Any]) -> ToolParserResult:
    group_fields = [
        str(attributes(field).get("name", ""))
        for field in as_list(child(raw_config, "GroupFields").get("Field"))
        if attributes(field).get("name")
    ]
    return ToolParserResult(
        normalized_config={
            "num_columns": int(text(raw_config.get("NumColumns"), "1") or "1"),
            "is_horizontal": str(attributes(raw_config.get("IsHorizontal")).get("value", "True")).lower() == "true",
            "group_fields": group_fields,
        }
    )
