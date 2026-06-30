from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class ToolParserResult:
    normalized_config: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def attributes(node: Any) -> dict[str, Any]:
    if isinstance(node, dict):
        attrs = node.get("attributes")
        if isinstance(attrs, dict):
            return attrs
    return {}


def text(node: Any, default: str = "") -> str:
    if isinstance(node, dict):
        if "text" in node:
            return str(node["text"])
    if node is None:
        return default
    return str(node)


def child(node: dict[str, Any], key: str) -> Any:
    value = node.get(key)
    if value is None:
        return {}
    return value

