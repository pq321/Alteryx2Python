from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, text, child
from alteryx2python.parser.tool_parsers.select_parser import parse_select_config


def parse_appendfields_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "cartesian_mode": text(raw_config.get("CartesianMode"), "Error"),
            **({'select_fields': parse_select_config(child(child(raw_config, 'SelectConfiguration'), 'Configuration')).normalized_config['select_fields']} if raw_config.get('SelectConfiguration') else {}),
        }
    )
