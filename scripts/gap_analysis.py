"""Gap analysis: full Alteryx tool inventory vs project parser/registry coverage."""
from __future__ import annotations

import json
from pathlib import Path

from alteryx2python.parser.xml_parser import TOOL_PARSERS, _normalize_tool_type
from alteryx2python.tools.registry import TOOL_REGISTRY

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
SAMPLE_IDS = json.loads((PROJ / "reports/rea_evidence/sample_plugin_ids.json").read_text(encoding="utf-8"))

# noisy false positives from regex scan (text inside expressions etc.)
import re as _re

_VALID_ID = _re.compile(r"^[A-Za-z0-9_.\\/ ]+$")
NOISE = {")>-1", "Transformation"}
NOISE = {n for n in NOISE if _VALID_ID.match(n) is None}

registry = TOOL_REGISTRY
registered = set(registry.list_tool_types())
parsers = set(TOOL_PARSERS)

rows = []
for plugin_id, count in SAMPLE_IDS.items():
    if plugin_id in NOISE or _VALID_ID.match(plugin_id) is None:
        continue
    tool_type = _normalize_tool_type(plugin_id)
    rows.append({
        "plugin_id": plugin_id,
        "count": count,
        "tool_type": tool_type,
        "has_parser": tool_type in parsers,
        "has_runtime": tool_type in registered,
    })

missing_parser = sorted({r["plugin_id"] for r in rows if not r["has_parser"]})
missing_runtime = sorted({r["tool_type"] for r in rows if not r["has_runtime"]})
print("distinct plugin ids (samples):", len(rows))
print()
print("== tools WITHOUT dedicated parser (fallback raw) ==")
for r in sorted(rows, key=lambda x: -x["count"]):
    if not r["has_parser"]:
        print(f"  {r[chr(99)+chr(111)+chr(117)+chr(110)+chr(116)]:>5}  {r[chr(112)+chr(108)+chr(117)+chr(103)+chr(105)+chr(110)+chr(95)+chr(105)+chr(100)]:<60} -> {r[chr(116)+chr(111)+chr(111)+chr(108)+chr(95)+chr(116)+chr(121)+chr(112)+chr(101)]}")
print()
print("== tool types WITHOUT runtime registration ==")
for t in missing_runtime:
    print("  ", t)
print()
print("== registered count:", len(registered), " parser count:", len(parsers))
