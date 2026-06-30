from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def _file_path(config_node: Any) -> str:
    configuration = child(config_node, "Configuration") if isinstance(config_node, dict) else {}
    return text(child(configuration, "File"), "")


def parse_runcommand_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "program_name": text(child(raw_config, "ProgramName"), ""),
            "arguments": text(child(raw_config, "Arguments"), ""),
            "working_dir": text(child(raw_config, "WorkingDir"), ""),
            "run_minimized": str(attributes(child(raw_config, "RunMinimized")).get("value", "False")).lower()
            == "true",
            "run_silent": str(attributes(child(raw_config, "RunSilent")).get("value", "False")).lower()
            == "true",
            "input_file": _file_path(child(raw_config, "InputConfiguration")),
            "output_file": _file_path(child(raw_config, "OutputConfiguration")),
        }
    )
