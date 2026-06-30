from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def parse_action_config(raw_config: dict[str, Any]) -> ToolParserResult:
    annotation = child(raw_config, "annotation")
    return ToolParserResult(
        normalized_config={
            "name": text(child(annotation, "Name"), ""),
            "description": text(child(annotation, "DefaultAnnotationText"), ""),
        }
    )
