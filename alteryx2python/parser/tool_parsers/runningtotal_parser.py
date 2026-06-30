from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def _field_names(node: Any) -> list[str]:
    return [
        str(attributes(field).get("field", ""))
        for field in as_list(child(node, "Field"))
        if attributes(field).get("field")
    ]


def parse_runningtotal_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "group_by_fields": _field_names(raw_config.get("GroupByFields", {})),
            "running_total_fields": _field_names(raw_config.get("RunningTotalFields", {})),
        }
    )
