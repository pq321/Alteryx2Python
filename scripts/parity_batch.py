"""Batch parity driver: instrument many workflows, then compare them all.

Usage:
    uv run python scripts/parity_batch.py plan    <workflow-or-dir> --root E:/tmp/parity_runs
    uv run python scripts/parity_batch.py attest  E:/tmp/parity_runs --outcomes outcomes.json --reviewer me
    uv run python scripts/parity_batch.py collect E:/tmp/parity_runs

plan    - prepare a probe-instrumented copy of every .yxmd under the target
          (one run directory per workflow); reports ready/blocked with reasons.
attest  - after Designer runs, import observed outcomes keyed by run directory.
collect - read every run's probes, compare node-by-node with the Python side,
          and write an aggregate summary (summary.json + summary.csv).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = [sys.executable, "-m", "alteryx2python.parity"]


def _sh(args: list[str]) -> dict:
    completed = subprocess.run(
        PY + args, capture_output=True, text=True, cwd=str(ROOT), timeout=600
    )
    try:
        return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {"_raw": (completed.stdout or "") + (completed.stderr or "")}


def _workflows(target: Path, output_root: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(
        path for path in target.rglob("*")
        if path.is_file() and path.suffix.lower() in {".yxmd", ".yxwz"}
        and not path.is_relative_to(output_root)
    )


def slug(path: Path) -> str:
    keep = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in path.stem)
    return keep[:80] or "workflow"


def cmd_plan(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for workflow in _workflows(Path(args.target).resolve(), root):
        identity = hashlib.sha256(str(workflow.resolve()).encode()).hexdigest()[:10]
        run_dir = root / f"{slug(workflow)}-{identity}"
        if (run_dir / "manifest.json").is_file() and (run_dir / "python.json").is_file():
            rows.append({"workflow": str(workflow), "run_dir": str(run_dir), "status": "already_prepared"})
            continue
        result = _sh(["prepare", str(workflow), "--output-dir", str(run_dir)])
        if result.get("status") == "prepared":
            rows.append({"workflow": str(workflow), "run_dir": str(run_dir), "designer_file": result["workflow"], "status": "ready"})
        else:
            reason = result.get("error") or result.get("_raw", "")[:200]
            rows.append({"workflow": str(workflow), "run_dir": "", "status": "blocked", "reason": reason})
    ready = [row for row in rows if row["status"] in {"ready", "already_prepared"}]
    blocked = [row for row in rows if row["status"] == "blocked"]
    (root / "plan.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ready: {len(ready)}  blocked: {len(blocked)}  total: {len(rows)}")
    for row in blocked[:15]:
        print(f"  BLOCKED {Path(row['workflow']).name}: {row.get('reason', '')[:120]}")
    if blocked:
        from collections import Counter

        reasons = Counter()
        for row in blocked:
            text = row.get("reason", "")
            marker = text.split(":")[-1].strip() if "adapter for:" in text else text[:40]
            reasons[marker] += 1
        print("  blocking tools:", dict(reasons.most_common(10)))
    print("next: run each instrumented workflow in Designer and record the actual outcome")
    return 0


def cmd_attest(args: argparse.Namespace) -> int:
    root: Path = args.root
    outcomes = json.loads(args.outcomes.read_text(encoding="utf-8-sig"))
    runs = {path.name: path for path in root.iterdir() if (path / "python.json").is_file()}
    errors = {}
    for name, outcome in outcomes.items():
        if name not in runs:
            errors[name] = "Unknown run"
            continue
        command = ["attest", str(runs[name]), "--status", outcome["status"], "--reviewer", args.reviewer]
        for field, option in (("failed_nodes", "--failed-node"), ("skipped_nodes", "--skipped-node")):
            for node_id in outcome.get(field, []):
                command.extend((option, str(node_id)))
        result = _sh(command)
        if result.get("status") != outcome["status"]:
            errors[name] = result.get("error", result)
    print(json.dumps({"attested": len(outcomes) - len(errors), "errors": errors}, ensure_ascii=False))
    return int(bool(errors))


def cmd_collect(args: argparse.Namespace) -> int:
    root: Path = args.root
    runs = [d for d in sorted(root.iterdir()) if (d / "python.json").is_file()]
    rows = []
    for run in runs:
        if not (run / "manual-review.json").exists():
            rows.append({"run": run.name, "status": "not_run_in_designer"})
            continue
        result = _sh(["collect", str(run), "--manual"])
        rows.append(
            {
                "run": run.name,
                "status": result.get("status", "unknown"),
                "issues": ";".join(result.get("issues", []) or [])[:200],
                "pending": ";".join(result.get("incomplete_evidence", []) or [])[:200],
            }
        )
    plan_file = root / "plan.json"
    if plan_file.is_file():
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        rows.extend(
            {"run": entry["workflow"], "status": "blocked", "issues": entry["reason"]}
            for entry in plan if entry["status"] == "blocked"
        )
    summary = {
        "total": len(rows),
        "match": sum(1 for row in rows if row["status"] == "match"),
        "mismatch": sum(1 for row in rows if row["status"] == "mismatch"),
        "not_run": sum(1 for row in rows if row["status"] == "not_run_in_designer"),
        "other": sum(1 for row in rows if row["status"] not in {"match", "mismatch", "not_run_in_designer"}),
        "rows": rows,
    }
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    with (root / "summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["run", "status", "issues", "pending"])
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False))
    for row in rows:
        if row["status"] not in {"match"}:
            print(f"  {row['status']:<20} {row['run']} {row.get('issues', '')[:100]}")
    return int(not rows or summary["match"] != summary["total"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("target")
    plan.add_argument("--root", type=Path, required=True)
    attest = sub.add_parser("attest")
    attest.add_argument("root", type=Path)
    attest.add_argument("--outcomes", type=Path, required=True)
    attest.add_argument("--reviewer", default="manual")
    collect = sub.add_parser("collect")
    collect.add_argument("root", type=Path)
    args = parser.parse_args()
    return {"plan": cmd_plan, "attest": cmd_attest, "collect": cmd_collect}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
