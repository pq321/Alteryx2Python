from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, text


def parse_directory_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "directory": text(raw_config.get("Directory")),
            "file_spec": text(raw_config.get("FileSpec"), "*.*"),
            "include_subdirs": str(attributes(raw_config.get("IncludeSubDirs")).get("value", "False")).lower()
            == "true",
        }
    )
