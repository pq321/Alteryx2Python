import io
import json
import os

import pytest

from alteryx2python.cli import main
from alteryx2python.workflow_generator import WorkflowBuilder


def test_demo_keeps_case_between_commands_and_requires_native_attestation(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    builder = WorkflowBuilder()
    source = builder.add_text_input(["Name"], [["sample"]])
    builder.connect(source, builder.add_csv_output("result.csv"))
    workflow = tmp_path / "sample.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")

    assert main(["demo", "inspect", str(workflow)]) == 0
    summary = capsys.readouterr().out
    assert "Graph: 2 nodes, 1 connections" in summary
    assert "Phase 2 compile: compiled" in summary
    assert "Next: demo designer" in summary

    assert main(["demo", "designer", "--prepare-only"]) == 0
    state = json.loads((tmp_path / "reports/demo/latest.json").read_text(encoding="utf-8"))
    case = tmp_path / state["case"]
    assert (case / "source-audit.json").is_file()
    assert (case / "audit.json").is_file()
    assert (case / "native/manifest.json").is_file()

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main(["demo", "compare"]) == 2
    captured = capsys.readouterr()
    assert "Observed Designer outcome" in captured.err
    assert "Input ended" in captured.out
    assert not (case / "native/manual-review.json").exists()
    assert not (case / "delivery").exists()


def test_demo_rejects_changed_workflow_after_inspection(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    builder = WorkflowBuilder()
    builder.add_text_input(["Name"], [["sample"]])
    workflow = tmp_path / "sample.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")

    assert main(["demo", "inspect", str(workflow)]) == 0
    workflow.write_text(builder.render() + "\n", encoding="utf-8")
    assert main(["demo", "designer", "--prepare-only"]) == 2
    assert "Workflow changed since inspection" in capsys.readouterr().out


@pytest.mark.skipif(os.name != "nt", reason="Windows preview associations")
def test_demo_deliver_opens_existing_code_at_saved_node_and_output(tmp_path, monkeypatch, capsys):
    from alteryx2python.parity import presentation

    case = tmp_path / "case"
    delivery = case / "delivery"
    output = delivery / "delivery-output" / "report.xlsx"
    output.parent.mkdir(parents=True)
    output.touch()
    script = delivery / "phase_two.py"
    script.touch()
    report = delivery / "acceptance.json"
    report.write_text('{"status":"match","standalone_execution":"match"}', encoding="utf-8")
    (delivery / "phase_two.manifest.json").write_text('{"nodes":[{"node_id":"138","line":42}]}', encoding="utf-8")
    (case / "presentation-result.json").write_text(json.dumps({"report": str(report), "node": "138"}), encoding="utf-8")
    opened = []
    monkeypatch.setattr(presentation.shutil, "which", lambda name: "code.exe" if name == "code.exe" else None)
    monkeypatch.setattr(presentation.subprocess, "Popen", opened.append)
    monkeypatch.setattr(presentation.os, "startfile", opened.append)

    assert main(["demo", "deliver", "--case", str(case)]) == 0
    assert opened == [["code.exe", "--goto", f"{script}:42"], str(output)]
    assert f"{script}:42 (node 138)" in capsys.readouterr().out
