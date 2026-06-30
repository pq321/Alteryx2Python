from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def _bool_attribute(node: Any, default: bool = False) -> bool:
    raw = attributes(node).get("value")
    if raw is None:
        return default
    return str(raw).lower() == "true"


def _text_or_empty(node: Any) -> str:
    value = text(node, "")
    return "" if value == "{}" else value


def parse_blobconvert_config(raw_config: dict[str, Any]) -> ToolParserResult:
    to_blob = _bool_attribute(child(raw_config, "ToBlob"))
    normalized = {
        "to_blob": to_blob,
        "field": _text_or_empty(child(raw_config, "to_Field" if to_blob else "from_Field")),
        "mode": _text_or_empty(child(raw_config, "to_Mode" if to_blob else "from_Mode")),
        "text_code_page": _text_or_empty(
            child(raw_config, "to_textCodePage" if to_blob else "from_textCodePage")
        ),
    }
    return ToolParserResult(normalized_config=normalized)
