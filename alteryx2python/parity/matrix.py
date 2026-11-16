"""Prepare a deterministic queue of installed Designer examples for parity."""

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from .runner import instrumented_path, prepare, write_json
from .scope import phase_one_scope


def prepare_sample_matrix(samples: Path, destination: Path, *, limit: int | None = None) -> dict:
    scope = phase_one_scope(samples)
    sources = defaultdict(set)
    for tool in scope["tools"]:
        for relative in tool["configured_examples"]:
            if Path(relative).suffix.lower() == ".yxmd":
                sources[relative].add(tool["tool_type"])

    destination.mkdir(parents=True, exist_ok=False)
    unqueued = {row["tool_type"] for row in scope["tools"]}
    considered = set()
    plan = []
    ready = 0
    while unqueued and (limit is None or ready < limit):
        candidates = [
            relative for relative, kinds in sources.items()
            if relative not in considered and kinds & unqueued
        ]
        if not candidates:
            break

        def priority(relative):
            kinds = sources[relative]
            chapter = Path(relative).parts[0]
            return (not chapter.startswith("02 "), -len(kinds & unqueued), len(kinds), relative)

        relative = min(candidates, key=priority)
        considered.add(relative)
        source = (samples / relative).resolve()
        stem = re.sub(r"[^\w-]", "_", source.stem)[:70]
        suffix = hashlib.sha256(relative.encode()).hexdigest()[:10]
        run = destination / f"{stem}-{suffix}"
        row = {"workflow": str(source), "tools": sorted(sources[relative])}
        try:
            manifest = prepare(source, run)
            capture = json.loads((run / "python.json").read_text(encoding="utf-8"))
            if not (manifest["probes"] or manifest["sink_files"]):
                raise ValueError("No data or sink checkpoints")
        except (ValueError, OSError, TypeError, KeyError, RuntimeError, NotImplementedError) as exc:
            row.update(status="blocked", reason=str(exc))
        else:
            row.update(
                status="ready", run_dir=str(run), designer_file=str(instrumented_path(run, manifest)),
                python_status=capture["status"],
            )
            ready += 1
            # A queued example is a candidate for coverage. The proof is earned by collection.
            unqueued.difference_update(node["tool_type"] for node in manifest["nodes"] if not node.get("skip_reason"))
        plan.append(row)
    write_json(destination / "plan.json", plan)
    summary = {"ready": ready, "blocked": len(plan) - ready, "tools_without_queued_case": sorted(unqueued)}
    write_json(destination / "matrix-summary.json", summary)
    return summary
