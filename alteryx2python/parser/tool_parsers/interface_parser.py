from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def _annotation_values(raw_config: dict[str, Any]) -> dict[str, str]:
    annotation = child(raw_config, "annotation")
    return {
        "name": text(child(annotation, "Name"), ""),
        "prompt": text(child(annotation, "DefaultAnnotationText"), ""),
    }


def parse_interface_value_config(raw_config: dict[str, Any]) -> ToolParserResult:
    values = _annotation_values(raw_config)
    name = text(child(raw_config, "Name"), values["name"])
    prompt = text(child(raw_config, "Prompt"), values["prompt"])
    default = text(child(raw_config, "Default"), text(child(raw_config, "DefaultValue"), prompt))
    return ToolParserResult(
        normalized_config={
            **values,
            "name": name,
            "prompt": prompt,
            "default_value": default,
            **({"required": text(child(raw_config, "Required"), "false").lower() in {"true", "1"}} if "Required" in raw_config else {}),
            **({"choices": [text(item) for item in raw_config["Option"]]} if isinstance(raw_config.get("Option"), list) else {}),
        }
    )


def parse_interface_layout_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(normalized_config=_annotation_values(raw_config))
