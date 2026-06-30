from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def parse_bloboutput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "file_name": text(child(raw_config, "FileName"), ""),
            "modify_method": text(child(raw_config, "ModifyMethod"), ""),
            "modify_filename_field": text(child(raw_config, "ModifyFilename_Field"), ""),
            "blob_field": text(child(raw_config, "BlobField"), ""),
        }
    )
