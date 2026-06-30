from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def _bool_attr(node: Any, default: bool = False) -> bool:
    value = attributes(node).get("value")
    if value is None:
        return default
    return str(value).strip().lower() == "true"


def parse_test_config(raw_config: dict[str, Any]) -> ToolParserResult:
    tests = []
    for test_node in as_list(child(child(raw_config, "Tests"), "Test")):
        tests.append(
            {
                "name": text(child(test_node, "Name")),
                "connection": text(child(test_node, "Connection")),
                "type": text(child(test_node, "Type")),
                "value": text(child(test_node, "Value")),
            }
        )
    return ToolParserResult(
        normalized_config={
            "tests": tests,
            "dont_report_subsequent": _bool_attr(child(raw_config, "DontReportSubsequent"), default=False),
        }
    )
