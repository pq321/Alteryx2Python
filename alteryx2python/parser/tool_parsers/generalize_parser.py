from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def _bool_attr(node: Any, name: str, default: bool = False) -> bool:
    value = attributes(node).get(name)
    if value is None:
        return default
    return str(value).lower() == "true"


def parse_generalize_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "spatial_field": text(child(raw_config, "SpatialObjectField"), ""),
            "include_source": _bool_attr(child(raw_config, "IncludeSourceInOutput"), "value", True),
            "threshold": text(child(raw_config, "Threshold"), ""),
            "units": text(child(raw_config, "Units"), ""),
            "layerwise": _bool_attr(child(raw_config, "Layerwise"), "value", False),
            "output_field": "SpatialObj_Generalize",
        }
    )
