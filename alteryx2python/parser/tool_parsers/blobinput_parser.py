from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def parse_blobinput_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "file_name": text(child(raw_config, "FileName"), ""),
            "modify_method": text(child(raw_config, "ModifyMethod"), ""),
            "modify_filename_field": text(child(raw_config, "ModifyFilename_Field"), ""),
            "stop_on_error": str(
                attributes(child(raw_config, "ModifyFilename_StopOnError")).get("value", "True")
            ).lower()
            == "true",
            "split_blobs": str(attributes(child(raw_config, "SplitBlobs")).get("value", "False")).lower()
            == "true",
            "blob_chunk_size": text(child(raw_config, "BlobChunkSize"), ""),
        }
    )
