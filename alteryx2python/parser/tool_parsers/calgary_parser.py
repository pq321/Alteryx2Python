from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.catalog_parser import _normalize_value
from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def _bool_attr(raw_config: dict[str, Any], key: str) -> bool:
    return attributes(child(raw_config, key)).get("value", "False") == "True"


def _int_attr(raw_config: dict[str, Any], key: str) -> int:
    value = attributes(child(raw_config, key)).get("value", "0")
    try:
        return int(str(value))
    except ValueError:
        return 0


def _query(raw_config: dict[str, Any]) -> dict[str, Any]:
    query = child(raw_config, "Query")
    query_text = text(query) if isinstance(query, dict) and "text" in query else ""
    return {"text": query_text}


def parse_calgaryinput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "root_file_name": text(child(raw_config, "RootFileName")),
            "linked_tables": _normalize_value(child(raw_config, "LinkedTables")),
            "query": _query(raw_config),
            "count_only": _bool_attr(raw_config, "CountOnly"),
            "skip_records": _int_attr(raw_config, "SkipRecords"),
            "max_records": _int_attr(raw_config, "MaxRecords"),
        }
    )


def _join_fields(raw_config: dict[str, Any]) -> list[dict[str, Any]]:
    fields = child(raw_config, "JoinFields")
    return [attributes(item) for item in as_list(child(fields, "Field"))]


def parse_calgaryjoin_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "root_file_name": text(child(raw_config, "RootFileName")),
            "linked_tables": _normalize_value(child(raw_config, "LinkedTables")),
            "count_only": _bool_attr(raw_config, "CountOnly"),
            "join_mode": _bool_attr(raw_config, "JoinMode"),
            "match_all": _bool_attr(raw_config, "MatchAll"),
            "output_unjoined": _bool_attr(raw_config, "OutputUnjoined"),
            "query": _query(raw_config),
            "join_fields": _join_fields(raw_config),
        }
    )


def _cross_count_fields(raw_config: dict[str, Any]) -> list[dict[str, Any]]:
    container = child(raw_config, "CrossCountFields")
    fields: list[dict[str, Any]] = []
    for custom in as_list(child(container, "CustomField")):
        entry: dict[str, Any] = {"name": attributes(custom).get("name", "")}
        values = []
        for value in as_list(child(custom, "Value")):
            values.append(attributes(child(value, "Field")))
        entry["values"] = values
        fields.append(entry)
    return fields


def parse_calgarycrosscount_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "root_file_name": text(child(raw_config, "RootFileName")),
            "linked_tables": _normalize_value(child(raw_config, "LinkedTables")),
            "query": _query(raw_config),
            "cross_count_fields": _cross_count_fields(raw_config),
        }
    )


def parse_calgarycrosscountappend_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return parse_calgarycrosscount_config(raw_config)


def parse_calgaryloader_config(raw_config: dict[str, Any]) -> ToolParserResult:
    container = child(raw_config, "Fields")
    fields = [attributes(item) for item in as_list(child(container, "Field"))]
    return ToolParserResult(
        normalized_config={
            "root_file_name": text(child(raw_config, "RootFileName")),
            "use_license_key": _bool_attr(raw_config, "UseLicenseKey"),
            "fields": fields,
        }
    )
