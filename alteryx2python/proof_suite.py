"""Configuration-specific proof ledger; missing cases never become certificates."""

from __future__ import annotations

import json
import re
from pathlib import Path

from alteryx2python.equivalence import run_node_equivalence
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.parity.runner import file_hash, write_json


def run_proof_suite(
    manifest_path: Path,
    output_dir: Path,
    *,
    engine: Path | None = None,
    timeout: int = 120,
):
    manifest_path = manifest_path.resolve()
    cases = json.loads(manifest_path.read_text(encoding="utf-8-sig"))["cases"]
    if not cases:
        raise ValueError("Proof suite requires at least one case")
    names = [case["name"] for case in cases]
    if len(names) != len(set(names)) or any(
        not re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in names
    ):
        raise ValueError("Case names must be unique simple directory names")
    # Validate every attribution before executing any case.
    sources = []
    for case in cases:
        source = (manifest_path.parent / case["workflow"]).resolve()
        workflow = XmlWorkflowParser().parse(source)
        requested = case.get("tools", [])
        actual = {node.tool_type for node in workflow.nodes}
        if not requested or set(requested) - actual:
            raise ValueError(
                f"Case {case['name']} must name tools actually present in its workflow"
            )
        sources.append(source)
    output_dir.mkdir(parents=True, exist_ok=False)
    results, tools = [], {}
    for case, source in zip(cases, sources):
        report = run_node_equivalence(
            source, output_dir / case["name"], engine=engine, timeout=timeout
        )
        result = {
            "name": case["name"],
            "workflow": str(source),
            "source_sha256": file_hash(source),
            "tools": case["tools"],
            "status": report["status"],
            "proven_scope": report["proven_scope"],
            "report": f"{case['name']}/report.json",
        }
        results.append(result)
        for tool in case["tools"]:
            tools.setdefault(tool, []).append(
                {"case": case["name"], "status": report["status"]}
            )
    summary = {
        status: sum(row["status"] == status for row in results)
        for status in ("match", "mismatch", "blocked", "incomplete")
    }
    report = {
        "manifest_sha256": file_hash(manifest_path),
        "summary": summary,
        "cases": results,
        "tool_cases": tools,
        "universal_equivalence_proven": False,
    }
    write_json(output_dir / "proof-ledger.json", report)
    return report
