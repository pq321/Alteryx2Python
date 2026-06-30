from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def parse_tile_config(raw_config: dict[str, Any]) -> ToolParserResult:
    group_fields = [
        str(attributes(field).get("name", ""))
        for field in as_list(child(raw_config, "GroupFields").get("Field"))
        if attributes(field).get("name")
    ]
    method = text(raw_config.get("Method"), "EqualRecords")
    normalized: dict[str, Any] = {"method": method, "group_fields": group_fields}
    if method == "EqualRecords":
        config = child(raw_config, "EqualRecords")
        normalized["num_tiles"] = int(attributes(config.get("NumTiles")).get("value", "1"))
        normalized["sort_field"] = text(config.get("EqualRecordsGroupField"))
    elif method == "EqualSum":
        config = child(raw_config, "EqualSum")
        normalized["sum_field"] = text(config.get("SumField"))
        normalized["num_tiles"] = int(attributes(config.get("NumTiles")).get("value", "1"))
    elif method == "SmartTile":
        config = child(raw_config, "SmartTile")
        normalized["field"] = text(config.get("Field"))
        normalized["name_field"] = text(config.get("NameField"), "Tile_Name")
    elif method == "Manual":
        config = child(raw_config, "Manual")
        normalized["field"] = text(config.get("Field"))
        normalized["cutoffs"] = [
            float(line.strip())
            for line in text(config.get("Cutoffs")).splitlines()
            if line.strip()
        ]
    elif method == "UniqueValue":
        config = child(raw_config, "UniqueValue")
        normalized["unique_fields"] = [
            str(attributes(field).get("field", ""))
            for field in as_list(child(child(config, "UniqueFields"), "Field"))
            if attributes(field).get("field")
        ]
        normalized["dont_sort"] = str(attributes(config.get("DontSort")).get("value", "False")).lower() == "true"
    return ToolParserResult(normalized_config=normalized)
