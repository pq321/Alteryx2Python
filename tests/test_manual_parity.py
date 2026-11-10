from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from alteryx2python.parity.manual import (
    attest_native,
    create_review_bundle,
    check_review_bundle,
)
from alteryx2python.parity.runner import (
    collect_native,
    compare_runs,
    prepare,
    runtime_hash,
)
from alteryx2python.parity.samples import generate_samples


def _run_pair(native_status="success", python_status="success"):
    snapshot = {
        "columns": ["x"],
        "schema": None,
        "rows": [[{"kind": "int", "value": "1"}]],
    }
    base = {
        "source_sha256": "same",
        "runtime_sha256": runtime_hash(),
        "status": python_status,
        "nodes": {
            "1": {
                "tool_type": "Filter",
                "status": python_status,
                "inputs": {},
                "outputs": {"Output": snapshot},
            }
        },
    }
    native, python = copy.deepcopy(base), copy.deepcopy(base)
    native.update(
        producer="alteryx", status=native_status, errors=["native detailed parse error"]
    )
    native["nodes"]["1"]["status"] = native_status
    python.update(producer="python", errors=["KeyError"])
    return native, python


def test_same_failure_matches_regardless_of_class_text_and_no_outputs():
    native, python = _run_pair("failed", "failed")
    native["nodes"]["1"]["outputs"] = {}
    python["nodes"]["1"]["outputs"] = {}
    assert compare_runs(native, python)["status"] == "match"
    assert compare_runs(native, python)["outcomes_match"] is True


def test_success_failure_mismatch_and_success_data_corruption():
    native, python = _run_pair("failed", "success")
    assert compare_runs(native, python)["status"] == "mismatch"


def test_both_failed_still_requires_all_node_outcomes():
    native, python = _run_pair("failed", "failed")
    native["nodes"]["2"] = {
        "tool_type": "Filter",
        "status": "not_run",
        "inputs": {},
        "outputs": {},
    }
    assert compare_runs(native, python)["status"] == "incomplete"
    native, python = _run_pair()
    assert compare_runs(native, python)["status"] == "match"
    python["nodes"]["1"]["outputs"]["Output"]["rows"][0][0]["value"] = "2"
    assert compare_runs(native, python)["status"] == "mismatch"


def test_native_outcome_confirmation_rejects_missing_evidence(tmp_path):
    source = generate_samples(tmp_path / "samples")[0]
    directory = tmp_path / "run"
    prepare(source, directory)
    with pytest.raises(ValueError, match="missing native output"):
        attest_native(directory, "success")
    with pytest.raises(ValueError, match="require failed node"):
        attest_native(directory, "failed")
    with pytest.raises(ValueError, match="not in"):
        attest_native(directory, "failed", failed_nodes=["999"])
    review = attest_native(
        directory, "failed", failed_nodes=["2"], note="Observed in Designer"
    )
    assert review["node_outcomes"]["2"] == "failed"
    assert collect_native(directory, manual=True)["status"] == "failed"


def test_generated_python_runs_and_human_review_cannot_pass_pending_nodes(tmp_path):
    source = generate_samples(tmp_path / "samples")[0]
    bundle = tmp_path / "bundle"
    create_review_bundle(source, bundle)
    import sys

    result = subprocess.run(
        [sys.executable, str(bundle / "workflow.py")], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert list((bundle / "python-results").glob("*.csv"))
    assert check_review_bundle(bundle)["status"] == "incomplete"
    review_path = bundle / "review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["native_status"] = "success"
    for node in review["nodes"]:
        node["native_status"] = node["python_status"]
        node["outputs_equal"] = True
    review_path.write_text(json.dumps(review), encoding="utf-8")
    assert check_review_bundle(bundle)["status"] == "match"
    review["nodes"][0]["outputs_equal"] = False
    review_path.write_text(json.dumps(review), encoding="utf-8")
    assert check_review_bundle(bundle)["status"] == "mismatch"


def test_failure_manual_review_does_not_require_equal_exception_words(tmp_path):
    source = generate_samples(tmp_path / "samples")[3]
    bundle = tmp_path / "bundle"
    create_review_bundle(source, bundle)
    import sys

    subprocess.run(
        [sys.executable, str(bundle / "workflow.py")], capture_output=True, check=True
    )
    review_path = bundle / "review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["native_status"] = "failed"
    for node in review["nodes"]:
        node["native_status"] = node["python_status"]
        node["outputs_equal"] = True
    review_path.write_text(json.dumps(review), encoding="utf-8")
    assert check_review_bundle(bundle)["status"] == "match"


def test_review_bundle_resolves_native_paths_and_detects_config_changes(tmp_path):
    import xml.etree.ElementTree as ET

    source = generate_samples(tmp_path / "samples")[0]
    tree = ET.parse(source)
    node = tree.getroot().find(".//Nodes/Node")
    ET.SubElement(
        node.find("Properties/Configuration"), "File"
    ).text = "data/input.csv|||Sheet1"
    tree.write(source, encoding="utf-8", xml_declaration=True)
    bundle = tmp_path / "bundle"
    manifest = create_review_bundle(source, bundle)
    assert (bundle / "original.yxmd").read_bytes() == source.read_bytes()
    native = ET.parse(bundle / manifest["native_workflow"])
    assert (
        native.find(".//File").text
        == str(source.parent / "data/input.csv") + "|||Sheet1"
    )
    assert manifest["path_rewrites"]
    import sys

    subprocess.run(
        [sys.executable, str(bundle / "workflow.py")], capture_output=True, check=True
    )
    (bundle / "python-runtime.local.json").write_text(
        '{"changed": true}', encoding="utf-8"
    )
    assert "runtime_config_changed" in check_review_bundle(bundle)["issues"]
