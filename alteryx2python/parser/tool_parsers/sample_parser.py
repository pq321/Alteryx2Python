from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_sample_config(raw_config: dict[str, Any]) -> ToolParserResult:
    group_fields = [
        str(attributes(field).get("name", ""))
        for field in as_list(child(raw_config, "GroupFields").get("Field", []))
        if attributes(field).get("name")
    ]
    return ToolParserResult(
        normalized_config={
            "mode": text(raw_config.get("Mode"), "First"),
            "n": int(text(raw_config.get("N"), "0") or "0"),
            "group_fields": group_fields,
        }
    )
