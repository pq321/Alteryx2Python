from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def parse_jupytercode_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        {
            "default_venv": text(child(raw_config, "DefaultVenv"), ""),
            "venv_name": text(child(raw_config, "vEnvName"), ""),
            "guid_dir": text(child(raw_config, "GuidDir"), ""),
            "jupyter_guid_dir": text(child(raw_config, "JupyterGuidDir"), ""),
            "production_mode_script": text(child(raw_config, "productionModeScript"), ""),
            "notebook": text(child(raw_config, "Notebook"), ""),
            "jupyter_production": text(child(raw_config, "JupyterProduction"), ""),
        }
    )
