"""Failure-propagation behavioural parity: no output is a matchable outcome."""
from __future__ import annotations

from alteryx2python.parity.behavior import compare_behavior_runs

RUNTIME = "runtime-hash"


def _native(node_status: str, with_output: bool) -> dict:
    return {
        "producer": "alteryx",
        "source_sha256": "s",
        "status": "failed",
        "nodes": {
            "1": {
                "tool_type": "TextInput",
                "status": node_status,
                "inputs": {},
                "outputs": (
                    {"Output": {"columns": ["A"], "schema": None, "rows": []}}
                    if with_output
                    else {}
                ),
            },
            "2": {"tool_type": "Filter", "status": "failed", "inputs": {}, "outputs": {}},
        },
        "missing": [{"node_id": "2", "file": "probe-0001.yxdb", "anchor": "True"}],
        "unreadable": [],
    }


def _python(second_status: str) -> dict:
    return {
        "producer": "python",
        "source_sha256": "s",
        "status": "failed",
        "runtime_sha256": RUNTIME,
        "nodes": {
            "1": {
                "tool_type": "TextInput",
                "status": "success",
                "inputs": {},
                "outputs": {"Output": {"columns": ["A"], "schema": None, "rows": []}},
            },
            "2": {"tool_type": "Filter", "status": second_status, "inputs": {}, "outputs": {}},
        },
    }


def test_downstream_no_output_matches_across_failed_and_not_run():
    """Native reports the downstream node failed (no probe written); Python
    marks it failed or not_run. Both mean 'no output' -> behavioural match,
    without comparing any error wording."""
    report = compare_behavior_runs(_native("success", True), _python("not_run"), RUNTIME)
    assert report["status"] == "match", report
    no_output = [c for c in report["comparisons"] if c["status"] == "no_output_match"]
    assert any(c["node_id"] == "2" for c in no_output)
    assert report["exception_text_compared"] is False


def test_downstream_output_disagreement_is_still_a_mismatch():
    bad = _python("success")
    bad["nodes"]["2"]["outputs"] = {"True": {"columns": ["A"], "schema": None, "rows": []}}
    report = compare_behavior_runs(_native("success", True), bad, RUNTIME)
    assert report["status"] == "mismatch"
    assert "node_2_outcome_mismatch" in report["issues"]


def test_missing_native_outputs_tolerated_when_both_workflows_failed():
    report = compare_behavior_runs(_native("success", True), _python("failed"), RUNTIME)
    # The missing probe list is evidence, not an incomplete-workflow blocker,
    # once both sides agree the run failed.
    assert "missing_native_outputs" not in report["incomplete_evidence"]
