from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def parse_autofield_config(raw_config: dict[str, Any]) -> ToolParserResult:
    fields = [
        str(attributes(field).get("field", ""))
        for field in as_list(child(raw_config, "Fields").get("Field", []))
        if attributes(field).get("field") and str(attributes(field).get("selected", "True")).lower() != "false"
    ]
    return ToolParserResult(normalized_config={"fields": fields})
