from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, text


def parse_generaterows_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "update_field": str(attributes(raw_config.get("UpdateField")).get("value", "False")).lower() == "true",
            "update_field_name": text(raw_config.get("UpdateField_Name")),
            "create_field_name": text(raw_config.get("CreateField_Name")),
            "create_field_type": text(raw_config.get("CreateField_Type")),
            "create_field_size": int(text(raw_config.get("CreateField_Size"), "0") or "0"),
            "expression_init": text(raw_config.get("Expression_Init")),
            "expression_cond": text(raw_config.get("Expression_Cond")),
            "expression_loop": text(raw_config.get("Expression_Loop")),
        }
    )
