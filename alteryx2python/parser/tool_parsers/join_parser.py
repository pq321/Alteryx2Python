from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_join_config(raw_config: dict[str, Any]) -> ToolParserResult:
    join_info_nodes = as_list(raw_config.get("JoinInfo", []))
    joins = [
        {
            "connection": attributes(join_info).get("connection", ""),
            "field": attributes(child(join_info, "Field")).get("field", ""),
        }
        for join_info in join_info_nodes
    ]
    select_config_node = child(raw_config, "SelectConfiguration")
    normalized = {
        "join_by_record_pos": str(attributes(raw_config).get("joinByRecordPos", "False")).lower() == "true",
        "joins": joins,
        "output_connection": attributes(child(select_config_node, "Configuration")).get("outputConnection", ""),
        "select_fields": [
            {
                "source": attributes(select_field).get("field", ""),
                "rename": attributes(select_field).get("rename", attributes(select_field).get("field", "")),
                "input": attributes(select_field).get("input", ""),
                "selected": str(attributes(select_field).get("selected", "True")).lower() == "true",
            }
            for select_field in as_list(child(child(select_config_node, "Configuration"), "SelectFields").get("SelectField", []))
        ],
    }
    return ToolParserResult(normalized_config=normalized)
