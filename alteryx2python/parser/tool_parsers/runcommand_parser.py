from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text
from alteryx2python.parser.tool_parsers.dbfileoutput_parser import parse_dbfileoutput_config


def parse_runcommand_config(raw_config: dict[str, Any]) -> ToolParserResult:
    write_source = child(child(raw_config, "OutputConfiguration") or {}, "Configuration") or {}
    read_results = child(child(raw_config, "InputConfiguration") or {}, "Configuration") or {}
    write_options = parse_dbfileoutput_config(write_source).normalized_config
    input_file = write_options.pop("file")
    output_file = text(child(read_results, "File"), "")
    return ToolParserResult(
        normalized_config={
            "program_name": text(child(raw_config, "ProgramName"), ""),
            "arguments": text(child(raw_config, "Arguments"), ""),
            "working_dir": text(child(raw_config, "WorkingDir"), ""),
            "run_minimized": str(attributes(child(raw_config, "RunMinimized")).get("value", "False")).lower()
            == "true",
            "run_silent": str(attributes(child(raw_config, "RunSilent")).get("value", "False")).lower()
            == "true",
            "input_file": input_file,
            "output_file": output_file,
            **({"write_source_options": write_options} if any(write_options.values()) else {}),
        }
    )
