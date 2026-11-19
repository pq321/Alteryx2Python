"""Build offline views of the captured checkpoints used in a presentation comparison."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import shutil
from pathlib import Path

from .snapshot import cell_comparison_key

_ASSETS = Path(__file__).with_name("table_view")


def _json(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _cell(cell):
    kind = cell["kind"]
    value = cell.get("value")
    if kind == "float":
        value = repr(float.fromhex(value))
    if kind in {"int", "decimal", "float"}:
        return [kind, value, cell_comparison_key(cell)]
    if kind in {"bytes", "image"}:
        payload = cell["value"] if kind == "bytes" else cell["png_base64"]
        label = f'{cell["width"]} × {cell["height"]} image' if kind == "image" else "Binary data"
        return [kind, label, hashlib.sha256(payload.encode("ascii")).hexdigest()]
    return [kind, value]


def _table_data(directory, snapshot, saved):
    if snapshot is None:
        return None
    key = id(snapshot)
    if key in saved:
        return saved[key]
    schema = snapshot.get("schema") or []
    data = {
        "columns": snapshot["columns"],
        "types": [field.get("type") for field in schema],
        "rows": [[_cell(cell) for cell in row] for row in snapshot["rows"]],
    }
    payload = _json(data).encode("ascii")
    digest = hashlib.sha256(payload).hexdigest()
    path = directory / f"{digest}.js"
    if not path.is_file():
        code = base64.b64encode(gzip.compress(payload, compresslevel=3, mtime=0)).decode("ascii")
        path.write_text(f'window.checkpointTables["{digest}"] = "{code}";\n', encoding="ascii")
    saved[key] = digest
    return digest


def write_table_reports(destination, native, python, parity, selection):
    """Attach one link per reported anchor; identical table data share one file."""
    selected_node, selected_anchor = selection
    artifact_nodes = {item.get("node_id") for item in parity["artifact_differences"]}
    flagged = artifact_nodes | {item.get("node_id") for item in parity["outcome_differences"]}
    unassessed = []
    known = {(item["node_id"], item.get("direction"), item.get("anchor")) for item in parity["comparisons"]}
    for owner in sorted((flagged | {selected_node}) - {None}):
        for direction in ("inputs", "outputs"):
            checkpoints = set().union(*(run["nodes"].get(owner, {}).get(direction, {}) for run in (native, python)))
            for anchor in sorted(checkpoints):
                if (owner, direction, anchor) not in known:
                    unassessed.append({"node_id": owner, "direction": direction, "anchor": anchor, "status": "unassessed"})
    assets = destination / "tables"
    saved = {}
    template = None
    for index, item in enumerate([*parity["comparisons"], *unassessed], 1):
        owner = item["node_id"]
        direction, anchor = item.get("direction"), item.get("anchor")
        if not direction or anchor == "*":
            continue
        selected = selected_node == owner and (not selected_anchor or selected_anchor == anchor)
        if item.get("duplicates_upstream") and not selected:
            continue
        if not (selected or item["status"] in {"mismatch", "incomplete"} or item.get("order_differences")
                or owner in flagged):
            continue
        sides = []
        for run in (native, python):
            snapshot = run["nodes"].get(owner, {}).get(direction, {}).get(anchor)
            raw = run.get("report_snapshots", {}).get((owner, direction, anchor), snapshot)
            sides.append((raw, raw is not snapshot))
        if all(snapshot is None for snapshot, _ in sides):
            continue
        if template is None:
            assets.mkdir()
            template = (_ASSETS / "index.html").read_text(encoding="utf-8")
            for filename in ("view.css", "view.js"):
                shutil.copyfile(_ASSETS / filename, assets / filename)
        left, right = (_table_data(assets, snapshot, saved) for snapshot, _ in sides)
        metadata = native["nodes"].get(owner) or python["nodes"][owner]
        config = {
            "title": f'Node {owner} · {metadata["tool_type"]} · {direction[:-1].title()} / {anchor}',
            "status": item["status"],
            "orderDifferences": item.get("order_differences", []),
            "hasReportFields": any(raw for _, raw in sides),
            "tables": [left, right],
        }
        data_scripts = "\n".join(f'<script src="{key}.js"></script>' for key in dict.fromkeys((left, right)) if key)
        html = template.replace("<!--DATA_SCRIPTS-->", data_scripts)
        html = html.replace("__CHECKPOINT_CONFIG__", _json(config).replace("<", r"\u003c"))
        path = assets / f"anchor-{index:04}.html"
        path.write_text(html, encoding="utf-8")
        item["table_report"] = path.relative_to(destination).as_posix()
    if extra := [item for item in unassessed if item.get("table_report")]:
        parity["unassessed_table_reports"] = extra
