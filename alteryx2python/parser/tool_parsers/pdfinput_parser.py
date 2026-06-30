from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def parse_pdfinput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        {
            "field": text(child(raw_config, "FieldSelect"), ""),
            "mode": text(child(raw_config, "ModeSelect"), ""),
            "pdf_directory": text(child(raw_config, "PDFDirectory"), ""),
        }
    )
