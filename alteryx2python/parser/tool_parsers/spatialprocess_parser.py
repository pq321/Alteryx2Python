from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child


def _bool_attr_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).lower() == "true"


def parse_spatialprocess_config(raw_config: dict[str, Any]) -> ToolParserResult:
    fields = attributes(child(raw_config, "SpatialObjFields"))
    action = attributes(child(raw_config, "Action"))
    return ToolParserResult(
        normalized_config={
            "field1": str(fields.get("field1", "")),
            "field2": str(fields.get("field2", "")),
            "action": str(action.get("action", "")),
            "no_empty": _bool_attr_value(action.get("noEmpty"), False),
            "output_field": "SpatialObj_Process",
        }
    )
