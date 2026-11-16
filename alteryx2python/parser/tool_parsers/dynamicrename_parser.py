from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_dynamicrename_config(raw_config: dict[str, Any]) -> ToolParserResult:
    mode = text(raw_config.get("RenameMode"), "")
    section = {
        "Add": "AddPrefixSuffix",
        "Remove": "RemovePrefixSuffix",
        "FirstRow": "FirstRow",
        "RightInputMetadata": "NamesFromMetadata",
        "RightInputRows": "NamesFromRows",
    }.get(mode, "")
    options = child(raw_config, section)
    normalized = {
        "rename_mode": mode,
        "expression": text(raw_config.get("Expression"), ""),
        "options": {name: text(value) for name, value in options.items()},
    }
    fields = child(raw_config, "Fields")
    if fields:
        normalized["selected_fields"] = {
            attrs["name"]: str(attrs.get("selected", "True")).lower() == "true"
            for field in as_list(fields.get("Field"))
            if (attrs := attributes(field)).get("name")
        }
    return ToolParserResult(normalized_config=normalized)
