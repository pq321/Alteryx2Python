from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def _bool_attr(node: Any, name: str, default: bool = False) -> bool:
    value = attributes(node).get(name)
    if value is None:
        return default
    return str(value).lower() == "true"


def _optional_text(raw_config: dict[str, Any], key: str) -> str:
    value = raw_config.get(key)
    if value is None:
        return ""
    return text(value, "")


def parse_buffer_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "spatial_field": text(child(raw_config, "SpatialObjectField"), ""),
            "include_source": _bool_attr(child(raw_config, "IncludeSourceInOutput"), "value", True),
            "generalize_to_one_percent": _bool_attr(child(raw_config, "GeneralizeToOnePercent"), "value", False),
            "buffer_size_source": text(child(raw_config, "BufferSizeSource"), ""),
            "buffer_size": text(child(raw_config, "BufferSizeSpecificValue"), ""),
            "buffer_size_field": _optional_text(raw_config, "BufferSizeField"),
            "units": text(child(raw_config, "Units"), ""),
        }
    )
