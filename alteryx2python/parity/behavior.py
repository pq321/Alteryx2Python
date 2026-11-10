"""User acceptance: equal outcomes, and equal successful data, not equal wording."""

from __future__ import annotations

from typing import Any

from .snapshot import compare_snapshots


def compare_behavior_runs(
    native: dict[str, Any], python: dict[str, Any], current_runtime_hash: str
) -> dict[str, Any]:
    issues: list[str] = []
    incomplete: list[str] = []
    comparisons: list[dict[str, Any]] = []
    for key in ("source_sha256",):
        if native.get(key) != python.get(key):
            issues.append(f"{key}_mismatch")
    if native.get("producer") != "alteryx" or python.get("producer") != "python":
        issues.append("invalid_producer")
    if python.get("runtime_sha256") != current_runtime_hash:
        issues.append("python_runtime_changed_or_unrecorded")
    outcomes = (native.get("status"), python.get("status"))
    if all(status in {"success", "failed"} for status in outcomes):
        if outcomes[0] != outcomes[1]:
            issues.append("workflow_outcome_mismatch")
    else:
        incomplete.append("workflow_outcome_unverified")
    both_failed = outcomes == ("failed", "failed")
    for node_id in sorted(set(native["nodes"]) | set(python["nodes"])):
        left = native["nodes"].get(node_id)
        right = python["nodes"].get(node_id)
        if left is None or right is None:
            incomplete.append(f"node_{node_id}_missing")
            continue
        if left["tool_type"] != right["tool_type"]:
            issues.append(f"node_{node_id}_tool_type_mismatch")
        if right.get("baseline"):
            incomplete.append(f"node_{node_id}_placeholder_execution")
        left_status, right_status = left.get("status"), right.get("status")
        known = {"success", "failed", "not_run"}
        if left_status in known and right_status in known:
            if left_status != right_status:
                issues.append(f"node_{node_id}_outcome_mismatch")
            if left_status != "success" or right_status != "success":
                continue
        else:
            incomplete.append(f"node_{node_id}_outcome_unverified")
        # Successful checkpoints remain comparable before a later failure.
        for direction in ("inputs", "outputs"):
            a, b = left.get(direction, {}), right.get(direction, {})
            for anchor in sorted(set(a) | set(b)):
                if anchor not in a or anchor not in b:
                    if both_failed and left_status != "success":
                        continue
                    diff = {"status": "incomplete", "reason": "missing_anchor"}
                else:
                    diff = compare_snapshots(a[anchor], b[anchor])
                comparisons.append(
                    {
                        "node_id": node_id,
                        "direction": direction,
                        "anchor": anchor,
                        **diff,
                    }
                )
    if native.get("unreadable"):
        incomplete.append("unreadable_native_outputs")
    if not both_failed and native.get("missing"):
        incomplete.append("missing_native_outputs")
    if outcomes == ("success", "success") and not comparisons:
        incomplete.append("no_successful_data_evidence")
    states = {item["status"] for item in comparisons}
    if "blocked" in outcomes:
        status = "blocked"
    elif issues or "mismatch" in states:
        status = "mismatch"
    elif incomplete or "incomplete" in states:
        status = "incomplete"
    else:
        status = "match"
    return {
        "profile": "behavioral",
        "status": status,
        "outcomes_match": outcomes[0] == outcomes[1]
        and outcomes[0] in {"success", "failed"},
        "native_status": outcomes[0],
        "python_status": outcomes[1],
        "issues": issues,
        "incomplete_evidence": incomplete,
        "comparisons": comparisons,
        "exception_text_compared": False,
        "physical_schema_required": False,
        "missing_native_outputs": native.get("missing", []),
        "unreadable_native_outputs": native.get("unreadable", []),
        "universal_equivalence_proven": False,
    }
