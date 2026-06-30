from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def parse_polybuild_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "spatial_field": str(attributes(child(raw_config, "SpatialObj")).get("field", "")),
            "group_field": str(attributes(child(raw_config, "GroupField")).get("field", "")),
            "build_type": text(child(raw_config, "BuildType"), ""),
            "sequence_field": str(attributes(child(raw_config, "SequenceField")).get("field", "")),
        }
    )
