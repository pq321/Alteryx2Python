from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_sample_config(raw_config: dict[str, Any]) -> ToolParserResult:
    legacy_values = _legacy_value_config(raw_config)
    if legacy_values:
        return ToolParserResult(normalized_config=legacy_values)

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


def _legacy_value_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    values = raw_config.get("Value")
    if isinstance(values, dict):
        value_items = [values]
    elif isinstance(values, list):
        value_items = values
    else:
        return {}
    by_name = {
        str(attributes(item).get("name", "")): text(item, "")
        for item in value_items
        if isinstance(item, dict)
    }
    if str(by_name.get("Number", "")).lower() == "true":
        return {"mode": "First", "n": int(by_name.get("NNumber", "0") or "0"), "group_fields": []}
    if str(by_name.get("Percent", "")).lower() == "true":
        return {"mode": "NPercent", "n": int(by_name.get("NPercent", "0") or "0"), "group_fields": []}
    return {}
