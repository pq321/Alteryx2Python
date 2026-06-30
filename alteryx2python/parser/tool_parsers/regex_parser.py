from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def _bool_value(node: Any, default: bool = False) -> bool:
    raw = attributes(node).get("value")
    if raw is None:
        return default
    return str(raw).strip().lower() == "true"


def parse_regex_config(raw_config: dict[str, Any]) -> ToolParserResult:
    parse_simple = child(raw_config, "ParseSimple")
    parse_complex = child(raw_config, "ParseComplex")
    match = child(raw_config, "Match")
    return ToolParserResult(
        normalized_config={
            "field": text(raw_config.get("Field")),
            "regex_expression": str(attributes(raw_config.get("RegExExpression", {})).get("value", "")),
            "case_insensitive": _bool_value(raw_config.get("CaseInsensitve"), default=True),
            "method": text(raw_config.get("Method"), "Match"),
            "replace_expression": str(attributes(raw_config.get("Replace", {})).get("expression", "")),
            "copy_unmatched": _bool_value(child(raw_config.get("Replace", {}), "CopyUnmatched"), default=True),
            "parse_simple": {
                "split_to_rows": _bool_value(child(parse_simple, "SplitToRows")),
                "root_name": text(child(parse_simple, "RootName"), text(raw_config.get("Field"))),
                "num_fields": int(str(attributes(child(parse_simple, "NumFields")).get("value", "1")) or "1"),
            },
            "parse_complex_fields": [
                str(attributes(field).get("field", ""))
                for field in as_list(child(parse_complex, "Field"))
                if attributes(field).get("field") and attributes(field).get("field") != "No Marked Groups Found"
            ],
            "match_field": text(child(match, "Field"), f"{text(raw_config.get('Field'))}_Matched"),
        }
    )
