from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def _annotation_values(raw_config: dict[str, Any]) -> dict[str, str]:
    annotation = child(raw_config, "annotation")
    return {
        "name": text(child(annotation, "Name"), ""),
        "prompt": text(child(annotation, "DefaultAnnotationText"), ""),
    }


def parse_interface_value_config(raw_config: dict[str, Any]) -> ToolParserResult:
    values = _annotation_values(raw_config)
    return ToolParserResult(
        normalized_config={
            **values,
            "default_value": values["prompt"],
        }
    )


def parse_interface_layout_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(normalized_config=_annotation_values(raw_config))
