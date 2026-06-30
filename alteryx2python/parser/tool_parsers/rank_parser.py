from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def parse_rank_config(raw_config: dict[str, Any]) -> ToolParserResult:
    modes = [
        str(attributes(mode).get("value", "Ordinal"))
        for mode in as_list(child(raw_config, "RankingModes").get("Mode", []))
    ] or ["Ordinal"]
    sort_fields = [
        {
            "field": str(attributes(field).get("field", "")),
            "order": str(attributes(field).get("order", "Ascending")),
        }
        for field in as_list(child(raw_config, "SortInfo").get("Field", []))
        if attributes(field).get("field")
    ]
    group_fields = [
        str(attributes(field).get("name", ""))
        for field in as_list(child(raw_config, "GroupFields").get("Field", []))
        if attributes(field).get("name")
    ]
    return ToolParserResult(
        normalized_config={
            "ranking_modes": modes,
            "sort_fields": sort_fields,
            "group_fields": group_fields,
        }
    )
