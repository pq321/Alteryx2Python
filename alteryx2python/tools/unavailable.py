"""Explicit prerequisites replace silent baseline passthrough execution."""

from __future__ import annotations

from typing import Any, Callable


class ToolUnavailableError(NotImplementedError):
    """A missing implementation/resource is a blocker, not an equivalent error."""


def unavailable_tool(tool_type: str, category: str = "") -> Callable:
    if (
        category in {"Connectors", "Connect", "AI Tools"}
        or "API" in tool_type
        or tool_type.startswith("CloudML")
    ):
        prerequisite = (
            "the configured external service, credentials and its Python adapter"
        )
    elif category in {
        "Address",
        "Demographic Analysis",
        "Behavior Analysis (Deprecated)",
        "Calgary",
    }:
        prerequisite = "the matching licensed local data/model format and a validated Python decoder"
    elif category in {
        "Text Mining",
        "Computer Vision",
        "Machine Learning",
        "Predictive",
    }:
        prerequisite = (
            "the configured model/package and a validated algorithm/output adapter"
        )
    else:
        prerequisite = "a Python adapter for this tool/configuration"

    def execute(
        inputs: dict[str, Any], config: dict[str, Any], context: Any
    ) -> dict[str, Any]:
        raise ToolUnavailableError(
            f"{tool_type} requires {prerequisite}; no passthrough result was produced"
        )

    execute.__name__ = f"unavailable_{tool_type}"
    return execute
