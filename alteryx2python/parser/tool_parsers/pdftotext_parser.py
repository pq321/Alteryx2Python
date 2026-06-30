from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def parse_pdftotext_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        {
            "language": text(child(child(raw_config, "TextExtractionLanguage"), "LanguageName"), ""),
            "extraction_mode": text(child(raw_config, "TextExtractionMode"), ""),
            "risk_score": text(child(raw_config, "TextExtractionRiskScore"), ""),
            "image_of_graphic_text": text(child(raw_config, "TextExtractionImageOfGraphicText"), ""),
            "path_input_value": text(child(raw_config, "PathInputValue"), ""),
            "path_is_workflow_dependency": attributes(child(raw_config, "PathInputValue")).get(
                "isWorkflowDependency", ""
            ),
            "path_input_mode": text(child(raw_config, "PathInputMode"), ""),
            "path_input_field": text(child(raw_config, "PathInputField"), ""),
            "output_options": child(raw_config, "OutputOptions"),
        }
    )
