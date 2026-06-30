from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def _bool_attribute(node: Any, default: bool = False) -> bool:
    raw = attributes(node).get("value")
    if raw is None:
        return default
    return str(raw).lower() == "true"


def parse_xmlparse_config(raw_config: dict[str, Any]) -> ToolParserResult:
    normalized = {
        "xml_field": text(child(raw_config, "XMLField")),
        "xml_element": text(child(raw_config, "XMLElement")),
        "child_values": _bool_attribute(child(raw_config, "ChildValues"), default=False),
        "outer_xml": _bool_attribute(child(raw_config, "OuterXML"), default=False),
        "parse_root": _bool_attribute(child(raw_config, "ParseRoot"), default=False),
        "ignore_errors": _bool_attribute(child(raw_config, "IgnoreErrors"), default=False),
    }
    return ToolParserResult(normalized_config=normalized)
