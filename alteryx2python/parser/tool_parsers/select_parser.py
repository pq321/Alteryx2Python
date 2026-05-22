from __future__ import annotations

from typing import Any


def parse_select_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    fields = raw_config.get("select_fields", [])
    parsed_fields: list[dict[str, Any]] = []
    for field in fields:
        parsed_fields.append(
            {
                "source": field["source"],
                "rename": field.get("rename", field["source"]),
                "dtype": field.get("dtype"),
            }
        )
    return {"select_fields": parsed_fields}