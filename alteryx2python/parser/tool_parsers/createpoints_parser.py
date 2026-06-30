from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def parse_createpoints_config(raw_config: dict[str, Any]) -> ToolParserResult:
    fields = attributes(child(raw_config, "Fields"))
    return ToolParserResult(
        normalized_config={
            "x_field": str(fields.get("fieldX", "")),
            "y_field": str(fields.get("fieldY", "")),
            "mode": text(child(raw_config, "Mode"), ""),
            "output_field": "Centroid",
        }
    )
