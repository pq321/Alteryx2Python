from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def parse_basicdataprofile_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "limit_unique_count": text(child(raw_config, "Limit_UniqueCount"), ""),
            "limit_unique_values_size": text(child(raw_config, "Limit_UniqueValuesSize"), ""),
            "is_metric": str(attributes(child(raw_config, "IsMetric")).get("value", "False")).lower() == "true",
        }
    )
