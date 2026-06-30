from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def _split_annotation(annotation_text: str) -> tuple[str, str]:
    lines = [line.strip() for line in annotation_text.splitlines() if line.strip()]
    if not lines:
        return "", ""
    expression = lines[0]
    message = "\n".join(lines[1:])
    return expression, message


def parse_error_config(raw_config: dict[str, Any]) -> ToolParserResult:
    annotation = child(raw_config, "annotation")
    annotation_text = text(child(annotation, "DefaultAnnotationText"), "")
    name = text(child(annotation, "Name"), "")
    expression, message = _split_annotation(annotation_text)
    return ToolParserResult(
        normalized_config={
            "expression": expression,
            "message": message or name,
            "name": name,
            "enforce": False,
        }
    )
