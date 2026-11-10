from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.catalog_parser import _normalize_value
from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def _coerce_bool(value: Any) -> bool:
    return str(value).strip().lower() in ("true", "1")


def parse_textbox_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """Canvas note box (AlteryxGuiToolkit.TextBox.TextBox)."""
    font = attributes(child(raw_config, "Font"))
    text_color = child(raw_config, "TextColor")
    fill = child(raw_config, "FillColor")
    shape = attributes(child(raw_config, "Shape"))
    justification = attributes(child(raw_config, "Justification"))
    return ToolParserResult(
        normalized_config={
            "text": text(child(raw_config, "Text")),
            "font": font,
            "text_color": attributes(text_color),
            "fill_color": attributes(fill) if not text(fill) else text(fill),
            "shape": shape.get("shape", ""),
            "justification": justification.get("Justification", ""),
        }
    )


def parse_htmlbox_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """Canvas HTML box (AlteryxGuiToolkit.HtmlBox.HtmlBox)."""
    hide = attributes(child(raw_config, "HideAddressBar"))
    return ToolParserResult(
        normalized_config={
            "url": text(child(raw_config, "URL")),
            "hide_address_bar": hide.get("value", "") == "True",
        }
    )


def _parse_container(raw_config: dict[str, Any]) -> dict[str, Any]:
    style = attributes(child(raw_config, "Style"))
    return {
        "caption": text(child(raw_config, "Caption")),
        "style": style,
        "disabled": attributes(child(raw_config, "Disabled")).get("value") == "True",
        "folded": attributes(child(raw_config, "Folded")).get("value") == "True",
    }


def parse_toolcontainer_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """Tool Container (AlteryxGuiToolkit.ToolContainer.ToolContainer)."""
    return ToolParserResult(normalized_config=_parse_container(raw_config))


def parse_controlcontainer_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """Control Container for analytic apps (AlteryxGuiToolkit.ControlContainer)."""
    return ToolParserResult(normalized_config=_parse_container(raw_config))


def parse_message_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """Message tool: emits engine messages at runtime."""
    return ToolParserResult(
        normalized_config={
            "when": text(child(raw_config, "When")),
            "filter": text(child(raw_config, "Filter")),
            "type": text(child(raw_config, "Type")),
            "priority": text(child(raw_config, "Priority")),
            "transient": _coerce_bool(text(child(raw_config, "Transient"))),
            "message_expression": text(child(raw_config, "MessageExpression")),
        }
    )


def parse_macrooutput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """Macro Output anchor definition (AlteryxBasePluginsGui.MacroOutput)."""
    normalized: dict[str, Any] = {
        "name": text(child(raw_config, "Name")),
        "anchor_name": text(child(raw_config, "AnchorName")),
        "optional": _coerce_bool(text(child(raw_config, "Optional"))),
    }
    for key, value in raw_config.items():
        if key not in normalized and key not in ("raw", "normalized", "base_dir"):
            normalized[key] = _normalize_value(value)
    return ToolParserResult(normalized_config=normalized)


def parse_blockuntildone_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """Block Until Done: buffers records until all upstream output closes."""
    return ToolParserResult(normalized_config={})
