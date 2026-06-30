from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child


def parse_joinmultiple_config(raw_config: dict[str, Any]) -> ToolParserResult:
    joins = []
    for join_info in as_list(child(raw_config, "JoinFields").get("JoinInfo")):
        connection = str(attributes(join_info).get("connection", ""))
        fields = [
            str(attributes(field).get("field", ""))
            for field in as_list(child(join_info, "Field"))
            if attributes(field).get("field")
        ]
        if connection and fields:
            joins.append({"connection": connection, "fields": fields})

    select_fields = []
    select_config = child(child(raw_config, "SelectConfiguration"), "Configuration")
    for field in as_list(child(select_config, "SelectFields").get("SelectField")):
        attrs = attributes(field)
        if attrs.get("field"):
            select_fields.append(
                {
                    "source": str(attrs.get("field", "")),
                    "selected": str(attrs.get("selected", "True")).lower() == "true",
                    "rename": str(attrs.get("rename", attrs.get("field", ""))),
                }
            )

    return ToolParserResult(
        normalized_config={
            "join_by_record_position": str(attributes(raw_config.get("JoinByRecPos")).get("value", "False")).lower()
            == "true",
            "joins": joins,
            "cartesian_mode": child(raw_config, "CartesianMode").get("text", "Error"),
            "output_join_only": str(attributes(raw_config.get("OutputJoinOnly")).get("value", "False")).lower()
            == "true",
            "select_fields": select_fields,
        }
    )
