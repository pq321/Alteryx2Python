from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def parse_unique_config(raw_config: dict[str, Any]) -> ToolParserResult:
    unique_fields = [
        str(attributes(field).get("field", ""))
        for field in as_list(child(raw_config, "UniqueFields").get("Field", []))
        if attributes(field).get("field")
    ]
    return ToolParserResult(normalized_config={"unique_fields": unique_fields})
