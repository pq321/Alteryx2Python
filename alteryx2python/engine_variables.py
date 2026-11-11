"""Engine variables and token substitution (reverse-engineered constants).

Two substitution systems run inside the native engine:

1. Percent tokens replaced in configuration strings BEFORE a tool executes:
   "%temp%" / "%TEMP%" (engine temp directory), "%Question.<Name>%" (analytic
   app / macro interface answers), and the "%Engine.<Name>%" spellings.
2. Expression constants referenced like fields inside formulas:
   [Engine.WorkflowDirectory], [Engine.WorkflowFileName],
   [Engine.TempFilePath], [Engine.ModuleDirectory], [Engine.IterationNumber],
   [Engine.OS], [Engine.Version], [Engine.Type], [Engine.ReportFont],
   [Engine.GuiInteraction] - names harvested from the shipped engine DLL
   string tables.

User variables: the engine has no separate user-variable store; user-defined
values enter through analytic app Questions (answers dict) or macro interface
values, both of which feed the "%Question.<Name>%" namespace here.
"""
from __future__ import annotations

import os
import platform
import re
from pathlib import Path
from typing import Any

QUESTION_TOKEN = re.compile(r"%Question\.([^%]+)%")
ENGINE_TOKEN = re.compile(r"%Engine\.([A-Za-z]+)%")
TEMP_TOKEN = re.compile(r"%temp%", re.IGNORECASE)

ENGINE_CONSTANT_NAMES = (
    "WorkflowDirectory",
    "WorkflowFileName",
    "TempFilePath",
    "ModuleDirectory",
    "IterationNumber",
    "OS",
    "Version",
    "Type",
    "ReportFont",
    "GuiInteraction",
)


def engine_constants(
    workflow_path: str | Path | None = None,
    *,
    temp_directory: str | None = None,
    iteration_number: int = 0,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the [Engine.X] constant table the expression layer can consult."""
    workflow_path = Path(workflow_path) if workflow_path else None
    module_directory = str(Path(__file__).resolve().parent.parent)
    values: dict[str, Any] = {
        "WorkflowDirectory": str(workflow_path.parent) if workflow_path else str(Path.cwd()),
        "WorkflowFileName": workflow_path.name if workflow_path else "",
        "TempFilePath": temp_directory or os.environ.get("TEMP", str(Path.cwd())),
        "ModuleDirectory": module_directory,
        "IterationNumber": iteration_number,
        "OS": platform.system() or "Windows",
        "Version": platform.python_version(),
        "Type": "Python",
        "ReportFont": "Segoe UI",
        "GuiInteraction": False,
    }
    if overrides:
        values.update({key: value for key, value in overrides.items() if key in ENGINE_CONSTANT_NAMES})
    return values


def resolve_tokens(
    text: str,
    *,
    answers: dict[str, Any] | None = None,
    constants: dict[str, Any] | None = None,
) -> str:
    """Substitute percent tokens in one configuration string.

    Substitution order mirrors the engine: question answers first, then
    engine tokens, then the classic temp shorthand. Unknown tokens are left
    untouched so diagnostics can spot them later.
    """
    if not isinstance(text, str) or "%" not in text:
        return text

    def _question(match: re.Match) -> str:
        name = match.group(1).strip()
        if answers and name in answers:
            return str(answers[name])
        return match.group(0)

    text = QUESTION_TOKEN.sub(_question, text)

    def _engine(match: re.Match) -> str:
        name = match.group(1)
        if constants and name in constants:
            return str(constants[name])
        return match.group(0)

    text = ENGINE_TOKEN.sub(_engine, text)
    temp = (constants or {}).get("TempFilePath") if constants else None
    if temp:
        text = TEMP_TOKEN.sub(lambda _match: str(temp), text)
    return text


def resolve_workflow_tokens(workflow, answers: dict[str, Any] | None = None) -> None:
    """Resolve percent tokens across every node config of a parsed workflow.

    Mutates node.config['normalized'] and node.config['raw'] in place; nodes
    without percent tokens are untouched. Used by the executor before graph
    execution and by the macro engine after binding macro interface answers.
    """
    constants = engine_constants(getattr(workflow, "source_file", None) or None)
    for node in getattr(workflow, "nodes", []):
        config = getattr(node, "config", None)
        if not isinstance(config, dict):
            continue
        for section in ("normalized", "raw"):
            if section in config:
                config[section] = resolve_config_tokens(
                    config[section], answers=answers, constants=constants
                )


def resolve_config_tokens(
    config: Any,
    *,
    answers: dict[str, Any] | None = None,
    constants: dict[str, Any] | None = None,
) -> Any:
    """Recursively substitute percent tokens through a parsed config tree."""
    if isinstance(config, str):
        return resolve_tokens(config, answers=answers, constants=constants)
    if isinstance(config, list):
        return [resolve_config_tokens(item, answers=answers, constants=constants) for item in config]
    if isinstance(config, dict):
        resolved = {}
        for key, value in config.items():
            new_key = resolve_tokens(str(key), answers=answers, constants=constants) if "%" in key else key
            resolved[new_key] = resolve_config_tokens(value, answers=answers, constants=constants)
        return resolved
    return config
