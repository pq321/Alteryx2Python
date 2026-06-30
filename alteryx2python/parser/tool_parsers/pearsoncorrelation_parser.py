from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def _bool_attr(node: Any, default: bool = False) -> bool:
    value = attributes(node).get("value")
    if value is None:
        return default
    return str(value).strip().lower() == "true"


def parse_pearsoncorrelation_config(raw_config: dict[str, Any]) -> ToolParserResult:
    fields = []
    for field in as_list(child(raw_config, "Fields").get("Field", [])):
        attrs = attributes(field)
        name = str(attrs.get("name", "")).strip()
        if not name:
            continue
        selected = str(attrs.get("selected", "True")).strip().lower() != "false"
        if selected:
            fields.append(name)
    return ToolParserResult(
        normalized_config={
            "fields": fields,
            "covariance": _bool_attr(child(raw_config, "Covariance"), default=False),
        }
    )
