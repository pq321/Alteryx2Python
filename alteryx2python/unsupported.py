from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_EXECUTION_TOOLS = {
    "CrossTab",
    "DbFileInput",
    "DbFileOutput",
    "DynamicRename",
    "Filter",
    "Formula",
    "JSONParse",
    "Join",
    "RecordID",
    "Select",
    "Transpose",
    "Union",
}

DEFERRED_INTERFACE_TOOLS = {
    "Action",
    "QuestionFileBrowse",
    "QuestionTab",
    "QuestionTextBox",
}

DEFERRED_OUTPUT_LIMITS = {
    "ExcelInput",
    "ExcelOutput",
    "YXDB",
    "DatabaseConnection",
}


@dataclass(frozen=True, slots=True)
class TriageDecision:
    classification: str
    reason: str


def classify_tool(tool_type: str) -> TriageDecision:
    if tool_type in SUPPORTED_EXECUTION_TOOLS:
        return TriageDecision("safe_to_attempt", "Tool has baseline runtime semantics")
    if tool_type in DEFERRED_INTERFACE_TOOLS:
        return TriageDecision("owner_review_required", "Interface/action semantics are deferred")
    if tool_type == "ToolContainer":
        return TriageDecision("parsed_only", "Container is structural and not directly executable")
    return TriageDecision("custom_code_required", "Tool has no registered baseline semantics")
