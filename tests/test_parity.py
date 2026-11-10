from __future__ import annotations

import copy
import json
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

from alteryx2python.parity.__main__ import main
from alteryx2python.parity.coverage import ToolsListParser, coverage_report
from alteryx2python.parity.runner import (
    capture_python, collect_native, compare_runs, execute_native, prepare, read_yxdb, runtime_hash, verify_manifest,
)
from alteryx2python.parity.samples import generate_samples
from alteryx2python.parity.snapshot import compare_snapshots, encode_value, frame_snapshot


def snapshot(values=("a", "a", None, "")):
    frame = pd.DataFrame({"name": list(values)}, dtype=object)
    frame.attrs["alteryx_schema"] = [{"name": "name", "type": "V_WString", "size": "64", "scale": None}]
    return frame_snapshot(frame)


def runs():
    base = {"status": "success", "source_sha256": "abc", "runtime_sha256": runtime_hash(), "errors": [], "warnings": [],
            "nodes": {"1": {"tool_type": "TextInput", "status": "success", "errors": [], "warnings": [],
                            "inputs": {}, "outputs": {"Output": snapshot()}}}}
    return {**copy.deepcopy(base), "producer": "alteryx"}, {**copy.deepcopy(base), "producer": "python"}


@pytest.mark.parametrize("value,kind", [(None, "null"), (pd.NA, "null"), (False, "bool"),
    (0, "int"), (0.0, "float"), (float("nan"), "float"), ("", "string"),
    ("中文🙂", "string"), (b"\x00\xff", "bytes"), (Decimal("1.20"), "decimal"), (date(2026, 11, 9), "date")])
def test_typed_cells(value, kind):
    assert encode_value(value)["kind"] == kind
    json.dumps(encode_value(value), allow_nan=False)


def test_unsupported_cell_is_not_stringified():
    with pytest.raises(TypeError):
        encode_value(object())


@pytest.mark.parametrize("values", [("a", None, "a", ""), ("a", "a", "", ""), ("a", None, "")])
def test_detects_order_null_empty_and_duplicate_loss(values):
    assert compare_snapshots(snapshot(), snapshot(values))["status"] == "mismatch"


def test_schema_mismatch_and_missing_schema_never_pass():
    expected = snapshot()
    actual = copy.deepcopy(expected)
    actual["schema"][0]["size"] = "32"
    assert compare_snapshots(expected, actual, profile="strict")["status"] == "mismatch"
    actual["schema"] = None
    assert compare_snapshots(expected, actual, profile="strict")["status"] == "incomplete"
    actual["schema"] = []
    assert compare_snapshots(expected, actual, profile="strict")["status"] == "incomplete"


def test_complete_evidence_matches_but_is_not_universal_proof():
    native, python = runs()
    result = compare_runs(native, python)
    assert result["status"] == "match"
    assert result["universal_equivalence_proven"] is False


def test_unknown_or_different_node_diagnostics_cannot_pass():
    native, python = runs()
    native["nodes"]["1"]["errors"] = None
    assert compare_runs(native, python)["status"] == "match"
    assert compare_runs(native, python, profile="strict")["status"] == "incomplete"
    native["nodes"]["1"]["errors"] = ["native failure"]
    assert compare_runs(native, python)["status"] == "match"
    assert compare_runs(native, python, profile="strict")["status"] == "mismatch"


def test_runtime_changes_are_detected():
    native, python = runs()
    python["runtime_sha256"] = "old-runtime"
    assert "python_runtime_changed_or_unrecorded" in compare_runs(native, python)["issues"]


def test_cli_coverage_gate_writes_report_and_fails_on_gaps(tmp_path):
    inventory = {"source_url": "test", "retrieved_at": "now", "html_sha256": "x", "tools": [
        {"name": "Future", "plugin_id": "FutureVendor.FutureTool", "category": "Future", "role": "Full"}]}
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(inventory), encoding="utf-8")
    assert main(["coverage", "--inventory", str(path), "--output", str(tmp_path / "coverage.json"), "--require-mapped"]) == 1


@pytest.mark.parametrize("change", ["hash", "warning", "error", "baseline", "values", "producer"])
def test_failed_dimensions_cannot_pass(change):
    native, python = runs()
    if change == "hash":
        python["source_sha256"] = "different"
    elif change in {"warning", "error"}:
        python[change + "s"] = ["different"]
    elif change == "baseline":
        python["nodes"]["1"]["baseline"] = True
    elif change == "values":
        python["nodes"]["1"]["outputs"]["Output"] = snapshot(("bad",))
    else:
        native["producer"] = "python"
    assert compare_runs(native, python, profile="strict")["status"] == "mismatch"


def test_missing_node_anchor_blocks_but_matching_failures_pass():
    native, python = runs()
    native["nodes"]["1"]["outputs"].clear()
    assert compare_runs(native, python)["status"] == "incomplete"
    native["nodes"].clear()
    assert compare_runs(native, python)["status"] == "incomplete"
    native, python = runs()
    native["status"] = python["status"] = "failed"
    assert compare_runs(native, python)["status"] == "match"
    native["status"] = "blocked"
    python["errors"] = ["a Python error"]
    assert compare_runs(native, python)["status"] == "blocked"


def test_official_table_reader_and_missing_identifier():
    parser = ToolsListParser()
    parser.feed('<h2>Preparation</h2><table><tr><th>Tool Name</th><th>XML Tool Name</th><th>User Role</th></tr>'
                '<tr><td>Filter</td><td>AlteryxBasePluginsGui.Filter.Filter</td><td>Full</td></tr>'
                '<tr><td>Future tool</td><td>FutureVendor.Tool</td><td>Add-on</td></tr></table>')
    report = coverage_report({"tools": parser.rows, "source_url": "official", "retrieved_at": "now", "html_sha256": "abc"})
    assert report["official_rows"] == 2
    assert report["mapped_rows"] == report["missing_rows"] == 1
    assert report["tools"][1]["tool_type"] is None
    assert report["tools"][1]["differential_status"] == "unverified"


def test_checked_in_inventory_has_every_row_and_categories():
    inventory = json.loads(Path("docs/tools/official_inventory.json").read_text(encoding="utf-8"))
    report = coverage_report(inventory)
    assert len(report["tools"]) == len(inventory["tools"]) >= 300
    assert {"AI Tools", "Connectors", "Spatial", "Interface"} <= report["categories"].keys()
    assert report["mapped_rows"] + report["missing_rows"] == report["official_rows"]


@pytest.fixture
def prepared(tmp_path):
    workflow = generate_samples(tmp_path / "samples")[0]
    directory = tmp_path / "run"
    prepare(workflow, directory)
    return workflow, directory


def test_instrumentation_preserves_graph_and_captures_disconnected_anchors(prepared):
    workflow, directory = prepared
    manifest = verify_manifest(directory)
    assert {(p["node_id"], p["anchor"]) for p in manifest["probes"]} == {
        ("1", "Output"), ("2", "True"), ("2", "False"), ("3", "Unique"), ("3", "Duplicates")}
    original = ET.parse(workflow).getroot()
    instrumented = ET.parse(directory / "instrumented.yxmd").getroot()
    for node in original.find("Nodes"):
        assert ET.tostring(node) == ET.tostring(instrumented.find(f"Nodes/Node[@ToolID='{node.get('ToolID')}']"))
    assert json.loads((directory / "python.json").read_text())["status"] == "success"
    with pytest.raises(FileExistsError):
        prepare(workflow, directory)


def test_changed_source_is_rejected(prepared):
    workflow, directory = prepared
    workflow.write_bytes(workflow.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Source workflow changed"):
        verify_manifest(directory)


def test_changed_instrumented_workflow_is_rejected(prepared):
    _, directory = prepared
    path = directory / "instrumented.yxmd"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Instrumented workflow changed"):
        verify_manifest(directory)


def test_native_license_and_timeout_are_blocked(prepared):
    _, directory = prepared
    completed = subprocess.CompletedProcess([], 2, b'Error - Alteryx Engine: The Feature "API or FlowChartMode" is not licensed.', b"")
    with patch("alteryx2python.parity.runner.subprocess.run", return_value=completed):
        assert execute_native(directory, Path("missing.exe"))["reason"] == "engine_license_unavailable"
    assert collect_native(directory)["status"] == "blocked"
    with pytest.raises(ValueError, match="already exist"):
        execute_native(directory, Path("missing.exe"))


def test_native_timeout_preserves_partial_logs(prepared):
    _, directory = prepared
    with patch("alteryx2python.parity.runner.subprocess.run", side_effect=subprocess.TimeoutExpired([], 1, output=b"partial")):
        assert execute_native(directory, Path("missing.exe"))["reason"] == "engine_timeout"
    assert (directory / "native-console.bin").read_bytes() == b"partial"


def test_manual_collection_never_assumes_success(prepared):
    _, directory = prepared
    with pytest.raises(ValueError, match="Missing native run"):
        collect_native(directory)
    native = collect_native(directory, manual=True)
    assert native["status"] == "incomplete"
    assert len(native["missing"]) == 5


def test_python_failure_capture_and_sample_cases(tmp_path):
    paths = generate_samples(tmp_path / "samples")
    results = {path.stem: capture_python(path) for path in paths}
    assert results["missing_field_error"]["status"] == "failed"
    assert results["missing_field_error"]["nodes"]["2"]["status"] == "failed"
    assert results["empty_branch"]["nodes"]["2"]["outputs"]["True"]["rows"] == []
    assert results["join_multiplicity"]["status"] == "success"


def test_unreadable_yxdb_is_an_explicit_failure(tmp_path):
    pytest.importorskip("yxdb")
    path = tmp_path / "broken.yxdb"
    path.write_bytes(b"bad")
    with pytest.raises(Exception, match="not a valid YXDB"):
        read_yxdb(path)


def test_saved_native_yxdb_preserves_null_unicode_and_ignores_sortinfo_fields():
    pytest.importorskip("yxdb")
    text = read_yxdb(Path("tests/fixtures/parity/native_textinput.yxdb"))
    assert text["rows"][1][1] == {"kind": "null"}
    assert text["rows"][3][1] == {"kind": "string", "value": "é🙂"}
    joined = read_yxdb(Path("tests/fixtures/parity/native_join.yxdb"))
    assert len(joined["schema"]) == len(joined["columns"]) == 4
    assert len(joined["rows"]) == 6
    assert [row[0]["value"] for row in joined["rows"]] == ["a", "a", "a", "a", "b", "c"]


def test_canonical_join_matches_saved_native_records():
    pytest.importorskip("yxdb")
    native = read_yxdb(Path("tests/fixtures/parity/native_join.yxdb"))
    actual = capture_python(Path("examples/parity/join_multiplicity.yxmd"))["nodes"]["3"]["outputs"]["Join"]
    diff = compare_snapshots(native, actual)
    assert diff["values_match"] is True
    assert diff["status"] == "match"  # Physical metadata is supplemental in the default profile.
    assert compare_snapshots(native, actual, profile="strict")["status"] == "incomplete"


def test_cli_prepare_and_manual_collect_exit_nonzero(prepared):
    _, directory = prepared
    assert main(["collect", str(directory), "--manual"]) == 1
    assert (directory / "comparison.json").exists()
    assert main(["collect", str(directory / "absent")]) == 2
