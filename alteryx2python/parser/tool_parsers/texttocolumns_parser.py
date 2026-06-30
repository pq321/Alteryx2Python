from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, text


def parse_texttocolumns_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "field": text(raw_config.get("Field")),
            "error_handling": text(raw_config.get("ErrorHandling"), "Last"),
            "root_name": text(raw_config.get("RootName"), text(raw_config.get("Field"))),
            "delimiters": str(attributes(raw_config.get("Delimeters", {})).get("value", "")),
            "num_fields": int(str(attributes(raw_config.get("NumFields", {})).get("value", "1")) or "1"),
            "flags": int(str(attributes(raw_config.get("Flags", {})).get("value", "0")) or "0"),
        }
    )
