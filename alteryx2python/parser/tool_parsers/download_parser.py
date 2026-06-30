from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def _bool_attribute(node: Any, default: bool = False) -> bool:
    raw = attributes(node).get("value")
    if raw is None:
        return default
    return str(raw).lower() == "true"


def _int_text(node: Any, default: int) -> int:
    raw = text(node, "")
    if not raw or raw == "{}":
        return default
    return int(raw)


def parse_download_config(raw_config: dict[str, Any]) -> ToolParserResult:
    headers_node = child(child(raw_config, "Headers"), "NameValues")
    payload_node = child(raw_config, "Payload")
    normalized = {
        "url_field": text(child(raw_config, "URLField")),
        "output_mode": text(child(raw_config, "OutputMode"), "String"),
        "code_page": text(child(raw_config, "CodePage"), "65001"),
        "encode_urls": _bool_attribute(child(raw_config, "EncodeURLs"), default=False),
        "headers": [
            {
                "name": str(attributes(item).get("name", "")),
                "value": str(attributes(item).get("value", "")),
            }
            for item in as_list(child(headers_node, "Item"))
        ],
        "payload": {
            "http_action": text(child(payload_node, "HTTPAction"), "GET"),
            "body_mode": text(child(payload_node, "QueryStringBodyMode"), ""),
            "field": text(child(payload_node, "Field"), ""),
        },
        "timeout": _int_text(child(raw_config, "Timeout"), 30),
        "num_connections": _int_text(child(raw_config, "numConnections"), 1),
    }
    return ToolParserResult(normalized_config=normalized)
