"""End-to-end tests for Child 3: un-staged package delivery & multi-case boundary verification."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tomllib
from xml.etree import ElementTree as ET

import pytest

from alteryx2python.cli import main
from alteryx2python.parity.migration import prepare_migration, resume_migration
from alteryx2python.workflow_generator import WorkflowBuilder


@pytest.mark.parametrize("default_date", ["2026-11-18", "", "9999-12-31"])
def test_migration_delivery_emits_unstaged_package_and_verifies_boundary_cases(tmp_path: Path, default_date: str):
    from tests.test_parity_behavior.test_migration import app_fixture

    source = app_fixture(tmp_path)
    document = ET.parse(source)
    document.find(".//Question[Name='report_date']/Default").text = default_date
    document.write(source, encoding="utf-8")
    selected = tmp_path / "selected.csv"
    selected.write_text("amount\n15\n30\n", encoding="utf-8")

    case_dir = tmp_path / "case"
    prepare_migration(source, case_dir, supplied={"report_date": "2026-11-20", "source_file": "selected.csv"})
    result = resume_migration(case_dir)

    frozen = (case_dir / "phase_one.py").read_text(encoding="utf-8")
    assert "selected.csv" not in frozen
    assert "2026-11-20" not in frozen
    assert result["phase_one_vs_phase_two"] == "match"
    assert result["standalone_execution"] == "match"

    pkg_dir = case_dir / "delivery/package"
    assert (pkg_dir / "pipeline.py").is_file()
    assert (pkg_dir / "config.toml").is_file()
    assert (pkg_dir / "cli.py").is_file()

    pipeline_py = (pkg_dir / "pipeline.py").read_text(encoding="utf-8")
    config_toml = (pkg_dir / "config.toml").read_text(encoding="utf-8")

    # Delivered pipeline.py has ZERO staged snapshot paths and ZERO hardcoded answer values!
    assert "inputs/1" not in pipeline_py
    assert "inputs/2" not in pipeline_py
    assert "selected.csv" not in pipeline_py
    assert "2026-11-20" not in pipeline_py
    # Default config.toml reflects the un-staged source defaults, not staged paths!
    assert 'source_file = "default.csv"' in config_toml
    assert tomllib.loads(config_toml)["parameters"]["report_date"] == default_date
    assert "2000-01-01" not in pipeline_py
    case_config = json.loads((case_dir / "delivery/case_config.json").read_text(encoding="utf-8"))
    assert case_config["parameters"]["report_date"] == "2026-11-20"

    # Multi-case boundary verification ran both parameter_perturbation and empty_input without recompiling!
    diff_report = json.loads((case_dir / "delivery/phase-one-vs-phase-two.json").read_text(encoding="utf-8"))
    assert diff_report["profile"] == "boundary_package"
    assert diff_report["boundary_cases"]["parameter_perturbation"]["status"] == "match"
    assert diff_report["boundary_cases"]["empty_input"]["status"] == "match"


def test_cli_readable_directory_emits_modular_package(tmp_path: Path, capsys):
    builder = WorkflowBuilder()
    src = builder.add_text_input(["k", "v"], [["a", "1"], ["b", "2"]])
    sink = builder.add_csv_output("out.csv")
    builder.connect(src, sink)
    wf_path = tmp_path / "simple.yxmd"
    wf_path.write_text(builder.render(), encoding="utf-8")

    out_pkg = tmp_path / "simple_pkg"
    rc = main(["readable", str(wf_path), "--output", str(out_pkg)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "package"
    assert (out_pkg / "pipeline.py").is_file()
    assert (out_pkg / "runner.py").is_file()
    assert (out_pkg / "config.toml").is_file()


def test_migration_uses_frozen_phase_one_when_original_is_missing(tmp_path: Path):
    builder = WorkflowBuilder()
    data = builder.add_text_input(["amount"], [["1"]])
    sink = builder.add_csv_output("out.csv")
    builder.connect(data, sink)
    source = tmp_path / "simple.yxmd"
    source.write_text(builder.render(), encoding="utf-8")
    case_dir = tmp_path / "case"
    prepare_migration(source, case_dir)
    source.rename(tmp_path / "moved.yxmd")

    result = resume_migration(case_dir)

    delivery = case_dir / "delivery"
    assert result["phase_one_vs_phase_two"] == "match"
    assert (case_dir / "phase_one.py").read_bytes() == (delivery / "phase_one.py").read_bytes()
    phase_one = json.loads((delivery / "phase-one-capture.json").read_text(encoding="utf-8"))
    phase_two = json.loads((delivery / "package/manifest.json").read_text(encoding="utf-8"))
    assert phase_one["phase_one_sha256"] == phase_two["phase_one_sha256"] == result["phase_one_sha256"]
    assert str(data) in phase_one["nodes"]

    with (case_dir / "phase_one.py").open("a", encoding="utf-8") as stream:
        stream.write("# Corrupt the attested artifact")
    blocked = resume_migration(case_dir)
    assert blocked["status"] == "blocked"
    assert "Phase 1 artifact changed" in blocked["failure"]["message"]
    assert not (case_dir / "delivery-2/package").exists()



@pytest.mark.skipif(os.name != "nt", reason="Windows preview associations")
def test_demo_deliver_prefers_package_pipeline_and_shows_config_path(tmp_path: Path, monkeypatch, capsys):
    from alteryx2python.parity import presentation

    case = tmp_path / "case"
    delivery = case / "delivery"
    pkg = delivery / "package"
    pkg.mkdir(parents=True)
    output = delivery / "delivery-output" / "report.csv"
    output.parent.mkdir(parents=True)
    output.write_text("x\n1\n", encoding="utf-8")

    pipeline_py = pkg / "pipeline.py"
    pipeline_py.write_text("def transform(df):\n    return df\n", encoding="utf-8")
    config_toml = pkg / "config.toml"
    config_toml.write_text("[parameters]\n", encoding="utf-8")
    (pkg / "manifest.json").write_text('{"nodes":[{"node_id":"10","line":1}]}', encoding="utf-8")

    report = delivery / "acceptance.json"
    report.write_text('{"status":"match","standalone_execution":"match"}', encoding="utf-8")
    (case / "presentation-result.json").write_text(
        json.dumps({"report": str(report), "node": "10"}), encoding="utf-8"
    )

    opened = []
    monkeypatch.setattr(presentation.shutil, "which", lambda name: "code.exe" if name == "code.exe" else None)
    monkeypatch.setattr(presentation.subprocess, "Popen", opened.append)
    monkeypatch.setattr(presentation.os, "startfile", opened.append)

    assert main(["demo", "deliver", "--case", str(case)]) == 0
    out_text = capsys.readouterr().out
    assert opened == [["code.exe", "--goto", f"{pipeline_py}:1"], str(output)]
    assert f"Config: {config_toml}" in out_text
