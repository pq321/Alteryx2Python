import pandas as pd

from alteryx2python.equivalence import compare_frames, run_node_equivalence


def test_null_and_empty_are_not_equivalent():
    assert not compare_frames(
        pd.DataFrame({"x": [None]}), pd.DataFrame({"x": [""]})
    ).matches


def test_row_counts_whitespace_and_identifier_zeroes_cannot_disappear():
    assert not compare_frames(
        pd.DataFrame({"x": [None]}), pd.DataFrame({"x": []})
    ).matches
    assert not compare_frames(
        pd.DataFrame({"x": [" 1"]}), pd.DataFrame({"x": ["1"]})
    ).matches
    assert not compare_frames(
        pd.DataFrame({"x": ["001"]}), pd.DataFrame({"x": ["1"]})
    ).matches


def test_native_blocker_cannot_pass_when_python_also_fails(tmp_path, monkeypatch):
    from alteryx2python import equivalence
    from alteryx2python.native_runner import NativeRunResult
    from alteryx2python.workflow_presets import render_preset

    path = tmp_path / "case.yxmd"
    path.write_text(
        render_preset("summarize", str(tmp_path / "native.csv")), encoding="utf-8"
    )
    monkeypatch.setattr(
        equivalence,
        "run_native",
        lambda *a, **kw: NativeRunResult(
            "engine-cmd", False, "unavailable", status="blocked"
        ),
    )

    def fail(*a, **kw):
        raise ValueError("bad expression")

    monkeypatch.setattr(equivalence, "run_python_workflow", fail)
    report = equivalence.run_equivalence(path)
    assert report["equivalent"] is None


def test_both_real_failures_match_regardless_of_error_text(tmp_path, monkeypatch):
    from alteryx2python import equivalence
    from alteryx2python.native_runner import NativeRunResult
    from alteryx2python.workflow_presets import render_preset

    path = tmp_path / "case.yxmd"
    path.write_text(
        render_preset("summarize", str(tmp_path / "native.csv")), encoding="utf-8"
    )
    monkeypatch.setattr(
        equivalence,
        "run_native",
        lambda *a, **kw: NativeRunResult(
            "engine-cmd", False, "Native error", returncode=2, status="failed"
        ),
    )

    def fail(*a, **kw):
        raise KeyError("Python other text")

    monkeypatch.setattr(equivalence, "run_python_workflow", fail)
    report = equivalence.run_equivalence(path)
    assert (
        report["equivalent"] is True
        and report["proven_scope"] == "workflow-failure-only"
    )


def test_node_equivalence_without_native_is_blocked(tmp_path):
    yxmd = tmp_path / "missing.yxmd"
    yxmd.write_text("<not-a-workflow />", encoding="utf-8")
    result = run_node_equivalence(yxmd, tmp_path / "evidence")
    assert result["status"] == "blocked"
    assert result["proven_scope"] == "none"


def test_node_equivalence_uses_real_native_fixture_probes(tmp_path, monkeypatch):
    """Offline replay of independently captured Designer outputs, never Python goldens."""
    import shutil
    from pathlib import Path
    from alteryx2python.parity import runner

    fixture = Path("docs/tools/evidence/2026-11-09/behavioral-update/designer-fixed")
    assert list(fixture.glob("probe-*.yxdb"))
    engine = tmp_path / "engine.exe"
    engine.write_bytes(b"not executed")

    def replay(directory, engine, timeout):
        for source in fixture.glob("probe-*.yxdb"):
            shutil.copyfile(source, directory / source.name)
        result = {
            "status": "success",
            "output_sha256": {
                p.name: runner.file_hash(p) for p in directory.glob("probe-*.yxdb")
            },
        }
        runner.write_json(directory / "native-run.json", result)
        return result

    monkeypatch.setattr(runner, "execute_native", replay)
    result = run_node_equivalence(
        Path("examples/parity/branch_duplicates_unicode.yxmd"),
        tmp_path / "proof",
        engine,
    )
    assert result["status"] == "match" and result["proven_scope"] == "node-outputs"
    assert len(result["comparison"]["comparisons"]) == 7


def test_proof_manifest_cannot_attribute_absent_tools(tmp_path, monkeypatch):
    import json
    from alteryx2python import proof_suite
    import pytest
    from alteryx2python.parity.samples import generate_samples

    source = generate_samples(tmp_path / "samples")[0]
    manifest = tmp_path / "cases.json"
    manifest.write_text(
        json.dumps(
            {"cases": [{"name": "case", "workflow": str(source), "tools": ["Join"]}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="actually present"):
        proof_suite.run_proof_suite(manifest, tmp_path / "bad")
    manifest.write_text(
        json.dumps(
            {"cases": [{"name": "case", "workflow": str(source), "tools": ["Filter"]}]}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        proof_suite,
        "run_node_equivalence",
        lambda *a, **kw: {"status": "blocked", "proven_scope": "none"},
    )
    report = proof_suite.run_proof_suite(manifest, tmp_path / "proof")
    assert report["summary"]["blocked"] == 1
    assert report["tool_cases"]["Filter"][0]["status"] == "blocked"
    assert not report["universal_equivalence_proven"]


def test_node_capture_does_not_write_original_workflow_output(tmp_path):
    from xml.etree import ElementTree as ET
    from alteryx2python.parity.runner import prepare
    from alteryx2python.workflow_presets import render_preset

    native_csv = tmp_path / "valuable-native.csv"
    native_csv.write_text(
        "preserve this independently produced oracle", encoding="utf-8"
    )
    source = tmp_path / "case.yxmd"
    source.write_text(render_preset("summarize", str(native_csv)), encoding="utf-8")
    evidence = tmp_path / "evidence"
    manifest = prepare(source, evidence)
    assert (
        native_csv.read_text(encoding="utf-8")
        == "preserve this independently produced oracle"
    )
    assert list((evidence / "python-outputs").glob("python-sink-*"))
    root = ET.parse(evidence / "instrumented.yxmd").getroot()
    actual_outputs = [
        n.findtext("Properties/Configuration/File")
        for n in root.iter("Node")
        if n.findtext("Properties/Configuration/File")
    ]
    assert str(native_csv) not in actual_outputs
