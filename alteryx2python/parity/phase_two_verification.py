"""Compare emitted Phase 2 stage boundaries during a diagnostic replay."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main():
    package, capture, report = map(Path, sys.argv[1:4])
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from alteryx2python.parity.snapshot import compare_snapshots, frame_snapshot

    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    with capture.open(encoding="utf-8") as stream:
        expected = json.load(stream)["nodes"]
    stages = {
        node["function"]: node for node in manifest["nodes"]
        if node.get("stage_boundary", True) and not node.get("optimization")
    }
    sys.path.insert(0, str(package))
    from audit_utils import AuditLogger
    from cli import main as run_package

    execute_stage = AuditLogger.run_stage
    compared = 0
    divergence = None

    def compare_stage(self, function, /, *args, **kwargs):
        nonlocal compared, divergence
        result = execute_stage(self, function, *args, **kwargs)
        node = stages.get(function.__name__)
        if divergence is not None or node is None:
            return result
        anchors = node["outputs"]
        outputs = result if isinstance(result, tuple) else (result,)
        baseline = expected.get(node["node_id"], {}).get("outputs", {})
        if len(anchors) != len(outputs):
            return result
        for anchor, frame in zip(anchors, outputs):
            if anchor not in baseline:
                continue
            diff = compare_snapshots(baseline[anchor], frame_snapshot(frame))
            compared += 1
            if diff["status"] != "match":
                divergence = {
                    "node_id": node["node_id"], "anchor": anchor, "function": function.__name__,
                    "line": node["line"], **diff,
                }
                break
        return result

    AuditLogger.run_stage = compare_stage
    try:
        return run_package(sys.argv[4:])
    finally:
        report.write_text(json.dumps({
            "compared_anchors": compared, "first_divergence": divergence,
        }, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
