from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from alteryx2python.parser.tool_catalog import CATALOG, catalog_entry_for_plugin
from alteryx2python.parser.xml_parser import TOOL_PARSERS
from alteryx2python.tools.registry import TOOL_REGISTRY

OFFICIAL_URL = (
    "https://help.alteryx.com/designer/current/en/tools/designer-tools-list.html"
)


class ToolsListParser(HTMLParser):
    """Read the official public table, independent of our local tool registry."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, str]] = []
        self.category = ""
        self._heading: list[str] | None = None
        self._cell: list[str] | None = None
        self._cells: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h2":
            self._heading = []
        elif tag == "tr":
            self._cells = []
        elif tag in {"td", "th"}:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._heading is not None:
            self._heading.append(data)
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self._heading is not None:
            self.category = " ".join("".join(self._heading).split())
            self._heading = None
        elif tag in {"td", "th"} and self._cell is not None:
            self._cells.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and len(self._cells) >= 3:
            name, identifier, role = self._cells[:3]
            if identifier and identifier != "XML Tool Name":
                self.rows.append(
                    {
                        "name": name,
                        "plugin_id": identifier,
                        "role": role,
                        "category": self.category,
                    }
                )


def refresh_inventory(destination: Path, url: str = OFFICIAL_URL) -> dict:
    request = Request(
        url, headers={"User-Agent": "Alteryx2Python local learning inventory"}
    )
    with urlopen(request, timeout=60) as response:
        content = response.read()
        resolved_url = response.url
    parser = ToolsListParser()
    parser.feed(content.decode("utf-8"))
    if len(parser.rows) < 100:
        raise ValueError(
            "Official tools table was not found; refusing to replace inventory"
        )
    snapshot = {
        "source_url": resolved_url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "html_sha256": hashlib.sha256(content).hexdigest(),
        "tools": parser.rows,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return snapshot


def coverage_report(inventory: dict) -> dict:
    rows = []
    for item in inventory["tools"]:
        entry = catalog_entry_for_plugin(item["plugin_id"])
        metadata = None
        if entry and entry.tool_type in TOOL_REGISTRY.list_tool_types():
            metadata = TOOL_REGISTRY.get(entry.tool_type)
        rows.append(
            {
                **item,
                "tool_type": entry.tool_type if entry else None,
                "mapped": entry is not None,
                "parser_registered": bool(entry and entry.tool_type in TOOL_PARSERS),
                "runtime_registered": metadata is not None,
                "maturity": metadata.maturity if metadata else None,
                "baseline": bool(
                    metadata and metadata.semantics_doc == "docs/tools/baseline.md"
                ),
                "implemented": bool(
                    metadata and metadata.execution_profile != "unavailable"
                ),
                "execution_profile": metadata.execution_profile
                if metadata
                else "unmapped",
                "differential_status": "unverified",
                "required_evidence": [
                    "valid_config",
                    "invalid_config",
                    "all_input_anchors",
                    "all_output_anchors",
                    "field_type_size_scale",
                    "null_empty_unicode",
                    "row_order_duplicates",
                    "empty_input",
                    "warnings_errors",
                    "workflow_composition",
                ],
            }
        )
    return {
        "source_url": inventory["source_url"],
        "retrieved_at": inventory["retrieved_at"],
        "html_sha256": inventory["html_sha256"],
        "official_rows": len(rows),
        "official_unique_ids": len({row["plugin_id"] for row in rows}),
        "mapped_rows": sum(row["mapped"] for row in rows),
        "mapped_unique_ids": len({row["plugin_id"] for row in rows if row["mapped"]}),
        "missing_rows": sum(not row["mapped"] for row in rows),
        "baseline_rows": sum(row["baseline"] for row in rows),
        "implemented_rows": sum(row["implemented"] for row in rows),
        "prerequisite_or_adapter_rows": sum(
            row["mapped"] and not row["implemented"] for row in rows
        ),
        "verified_rows": 0,
        "local_catalog_entries": len(CATALOG),
        "categories": dict(Counter(row["category"] for row in rows)),
        "universal_equivalence_proven": False,
        "tools": rows,
    }
