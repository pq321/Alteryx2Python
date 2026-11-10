from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_summarize_config(raw_config: dict[str, Any]) -> ToolParserResult:
    fields = []
    for field in as_list(child(raw_config, "SummarizeFields").get("SummarizeField", [])):
        attrs = attributes(field)
        fields.append(
            {
                "field": str(attrs.get("field", "")),
                "action": str(attrs.get("action", "")),
                "rename": str(attrs.get("rename", attrs.get("field", ""))),
                "concat_start": _concat_text(child(field, "Concat_Start")),
                "separator": _concat_text(child(field, "Separator")),
                "concat_end": _concat_text(child(field, "Concat_End")),
            }
        )
    return ToolParserResult(normalized_config={"summarize_fields": fields})


def _concat_text(node: Any) -> str:
    value = text(node, "")
    if value == "{}":
        return ""
    return value.replace("\\r", "\r").replace("\\n", "\n")
