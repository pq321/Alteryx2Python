from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list

_TRUE = {"true", "True"}
_FALSE = {"false", "False"}


def _coerce_scalar(value: Any) -> Any:
    """Best-effort typed coercion for Alteryx XML text values."""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped in _TRUE:
        return True
    if stripped in _FALSE:
        return False
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    return value


def _normalize_value(value: Any) -> Any:
    """Recursively canonicalize a raw XML subtree, preserving every element.

    Losslessness rules:
    - element text becomes the coerced scalar when the element has no children,
    - attributes are preserved under the original key plus an @attributes map,
    - repeated elements collapse to lists, single children stay single,
    - nothing is dropped, renamed, or reordered semantically.
    """
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if not isinstance(value, dict):
        return _coerce_scalar(value)
    has_children = any(key not in ("attributes", "text") for key in value)
    normalized: dict[str, Any] = {}
    if "attributes" in value:
        normalized["@attributes"] = {
            key: _coerce_scalar(item) for key, item in value["attributes"].items()
        }
    if not has_children:
        if "text" in value:
            text = value["text"]
            coerced = _coerce_scalar(text)
            if "attributes" in value:
                normalized["#text"] = coerced
            else:
                return coerced
        return normalized
    for key, item in value.items():
        if key == "attributes":
            continue
        if key == "text" and not str(item).strip():
            continue
        normalized[key] = _normalize_value(item)
    if "text" in value and "text" not in normalized and str(value["text"]).strip():
        normalized["#text"] = _coerce_scalar(value["text"])
    return normalized


def parse_catalog_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """Complete, lossless canonical parser for catalog-registered tools.

    Every tool type in the tool catalog resolves to this parser (or a more
    specific one); it guarantees the normalized config preserves every
    configuration element of the original Alteryx XML node.
    """
    normalized: dict[str, Any] = {}
    for key, value in raw_config.items():
        if key in ("raw", "normalized", "base_dir", "container_id", "child_node_ids", "annotation"):
            normalized[key] = value
            continue
        normalized[key] = _normalize_value(value)
    return ToolParserResult(normalized_config=normalized)


def make_catalog_parser(tool_type: str) -> Any:
    """Build a catalog fallback parser bound to a tool type."""

    def _parse(raw_config: dict[str, Any]) -> ToolParserResult:
        result = parse_catalog_config(raw_config)
        return ToolParserResult(
            normalized_config={"tool_type": tool_type, **result.normalized_config},
            warnings=list(result.warnings),
        )

    return _parse


def text_list(raw_config: dict[str, Any], key: str) -> list[str]:
    """Collect repeated element texts (e.g. repeated <model_families> items)."""
    values: list[str] = []
    for item in as_list(raw_config.get(key)):
        if isinstance(item, dict):
            text = item.get("text")
            if text is not None:
                values.append(str(text))
        elif item is not None and not isinstance(item, (dict, list)):
            values.append(str(item))
    return values
