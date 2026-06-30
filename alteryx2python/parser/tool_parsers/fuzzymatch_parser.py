from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import (
    ToolParserResult,
    as_list,
    attributes,
    child,
    text,
)


def _bool_attr(node: Any, default: bool = False) -> bool:
    value = attributes(node).get("value", str(default))
    return str(value).lower() == "true"


def _float_attr(node: Any, default: float = 0.0) -> float:
    value = attributes(node).get("value", default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _match_fields(match_fields_node: Any) -> list[dict[str, Any]]:
    fields = []
    for field in as_list(child(match_fields_node, "MatchField")):
        style = child(field, "Style")
        fields.append(
            {
                "field_name": text(child(field, "FieldName"), ""),
                "style_name": attributes(style).get("Name", ""),
                "match_function": text(child(child(style, "Match"), "MatchFunction"), ""),
                "match_threshold": _float_attr(child(child(style, "Match"), "MatchThreshold"), 0.0),
            }
        )
    return fields


def parse_fuzzymatch_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        {
            "record_id_field": text(child(raw_config, "RecordIdField"), ""),
            "source_id_field": text(child(raw_config, "SourceIdField"), ""),
            "match_threshold": _float_attr(child(raw_config, "MatchThreshold"), 0.0),
            "output_score": _bool_attr(child(raw_config, "OutputScore")),
            "output_key": _bool_attr(child(raw_config, "OutputKey")),
            "output_unmatched": _bool_attr(child(raw_config, "OutputUnmatched")),
            "output_make_group": _bool_attr(child(raw_config, "OutputMakeGroup")),
            "generate_keys": _bool_attr(child(raw_config, "GenerateKeys")),
            "merge_mode": _bool_attr(child(raw_config, "MergeMode")),
            "match_fields": _match_fields(child(raw_config, "MatchFields")),
        }
    )
