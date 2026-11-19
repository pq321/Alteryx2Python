"""User acceptance: equal outcomes, and equal successful data, not equal wording."""

from __future__ import annotations

from typing import Any

from .snapshot import compare_snapshots

_ORDER_SENSITIVE_INPUTS = {"MultiRowFormula", "RecordID", "RunningTotal", "Sample"}


def _mark_repeated_inputs(native, python, comparisons):
    outputs = {
        (item["node_id"], item["anchor"]): item["status"]
        for item in comparisons if item.get("direction") == "outputs"
    }
    for item in comparisons:
        if item.get("direction") != "inputs" or item["status"] != "mismatch":
            continue
        owner, anchor = item["node_id"], item["anchor"]
        source = native.get("input_sources", {}).get(owner, {}).get(anchor)
        if not source or outputs.get((source["node_id"], source["anchor"])) != "mismatch":
            continue
        for run in (native, python):
            source_node = run["nodes"].get(source["node_id"], {})
            output = source_node.get("outputs", {}).get(source["anchor"])
            receiving = run["nodes"][owner]["inputs"][anchor]
            if output is None or (output is not receiving and
                                  any(output.get(key) != receiving.get(key) for key in ("columns", "rows"))):
                break
        else:
            item["duplicates_upstream"] = source


def compare_behavior_runs(
    native: dict[str, Any], python: dict[str, Any], current_runtime_hash: str, *, align_checkpoints: bool = False,
) -> dict[str, Any]:
    issues: list[str] = []
    incomplete: list[str] = []
    comparisons: list[dict[str, Any]] = []
    artifact_differences = []
    outcome_differences = []
    for key in ("source_sha256", "answers"):
        if native.get(key) != python.get(key):
            issues.append(f"{key}_mismatch")
    if native.get("producer") != "alteryx" or python.get("producer") != "python":
        issues.append("invalid_producer")
    if python.get("runtime_sha256") != current_runtime_hash:
        issues.append("python_runtime_changed_or_unrecorded")
    for key in ("event_artifacts", "sink_artifacts", "render_digests"):
        if key not in native:
            continue
        if native.get(key) is None or python.get(key) is None:
            incomplete.append(f"{key}_unverified")
        elif native[key] != python[key]:
            issues.append(f"{key}_mismatch")
            artifact_differences.extend(
                {"group": key, "key": name, "status": status}
                for name, status in changed_artifacts(native[key], python[key])
            )
    outcomes = (native.get("status"), python.get("status"))
    if all(status in {"success", "failed"} for status in outcomes):
        if outcomes[0] != outcomes[1]:
            issues.append("workflow_outcome_mismatch")
            outcome_differences.append({"expected": outcomes[0], "actual": outcomes[1]})
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
            outcome_differences.append({"node_id": node_id, "dimension": "tool type",
                                        "expected": left["tool_type"], "actual": right["tool_type"]})
        if right.get("baseline"):
            incomplete.append(f"node_{node_id}_placeholder_execution")
        left_status, right_status = left.get("status"), right.get("status")
        if "skipped" in (left_status, right_status):
            if left_status != right_status or left.get("outputs") or right.get("outputs"):
                issues.append(f"node_{node_id}_skip_mismatch")
                outcome_differences.append({"node_id": node_id, "dimension": "skip status",
                                            "expected": left_status, "actual": right_status})
            else:
                comparisons.append({
                    "node_id": node_id,
                    "status": "skipped",
                    "reason": left.get("skip_reason") or right.get("skip_reason"),
                })
            continue
        known = {"success", "failed", "not_run"}
        if left_status in known and right_status in known:
            no_output = {"failed", "not_run"}
            if left_status == "success" and right_status == "success":
                pass  # both produced output: compare the data below
            elif left_status in no_output and right_status in no_output:
                # Both sides agree the node produced no output (an upstream
                # failure propagates as failed or not_run). Matching the
                # absence of output is the behavioural contract; replicating
                # native error wording is explicitly out of scope.
                comparisons.append(
                    {
                        "node_id": node_id,
                        "direction": "outputs",
                        "anchor": "*",
                        "status": "no_output_match",
                        "native_status": left_status,
                        "python_status": right_status,
                    }
                )
                continue
            else:
                issues.append(f"node_{node_id}_outcome_mismatch")
                outcome_differences.append({"node_id": node_id, "expected": left_status, "actual": right_status})
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
                    diff = {"status": "incomplete", "reason": "missing_anchor",
                            "missing_from": "Designer" if anchor not in a else "Phase 1"}
                else:
                    tool_type = left["tool_type"]
                    preserve_row_order = (
                        tool_type == "Sort" if direction == "outputs" else tool_type in _ORDER_SENSITIVE_INPUTS
                    )
                    diff = compare_snapshots(a[anchor], b[anchor], align_columns=align_checkpoints,
                                             align_rows=align_checkpoints and not preserve_row_order)
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
    if outcomes == ("success", "success") and not any(
        item["status"] == "match" for item in comparisons
    ):
        incomplete.append("no_successful_data_evidence")
    if align_checkpoints:
        _mark_repeated_inputs(native, python, comparisons)
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
        "artifact_differences": artifact_differences,
        "outcome_differences": outcome_differences,
        "exception_text_compared": False,
        "physical_schema_required": False,
        **({"align_checkpoints": True} if align_checkpoints else {}),
        "missing_native_outputs": native.get("missing", []),
        "unreadable_native_outputs": native.get("unreadable", []),
        "universal_equivalence_proven": False,
    }



def changed_artifacts(expected, actual):
    for name in sorted(expected.keys() | actual.keys()):
        if name not in expected:
            yield name, "unexpected"
        elif name not in actual:
            yield name, "missing"
        elif expected[name] != actual[name]:
            yield name, "different"
