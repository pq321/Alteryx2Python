import io
import json
import os
from xml.etree import ElementTree as ET

import pytest

from alteryx2python.cli import main
from alteryx2python.workflow_generator import WorkflowBuilder


def test_demo_keeps_case_between_commands_and_requires_native_evidence(tmp_path, monkeypatch, capsys):
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
    assert "Observed Designer outcome" not in captured.err
    assert "No Designer run evidence" in captured.out
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


def test_demo_compares_without_prompt_and_presents_both_outputs_on_mismatch(tmp_path, monkeypatch, capsys):
    import pandas as pd

    from alteryx2python.parity import designer_evidence, runner
    from alteryx2python.parity.snapshot import frame_snapshot
    from alteryx2python.parity.migration import prepare_migration

    builder = WorkflowBuilder()
    source = builder.add_text_input(["Name"], [["sample"]])
    sink = builder.add_csv_output("result.csv")
    builder.connect(source, sink)
    workflow = tmp_path / "sample.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    case = tmp_path / "case"
    launch = prepare_migration(workflow, case)
    manifest = runner.verify_manifest(case / "native")
    probe, = manifest["probes"]
    path = case / "native" / probe["file"]
    path.write_text(json.dumps(frame_snapshot(pd.DataFrame({"Name": ["sample"]}))), encoding="utf-8")
    for module in (runner, designer_evidence):
        monkeypatch.setattr(module, "read_yxdb", lambda filename: json.loads(filename.read_text(encoding="utf-8")))
    original = case / "native" / manifest["sink_files"][str(sink)]
    original.write_bytes(b"Name\r\nDifferent\r\n")
    runner.write_json(case / "designer-run.json", [
        {"status": "outputs_ready", "workflow": launch["native_workflow"]},
    ])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    assert main(["demo", "compare", "--case", str(case)]) == 1
    assert "Designer outcome: success" in capsys.readouterr().out
    assert not (case / "native/manual-review.json").exists()
    assert main(["demo", "deliver", "--case", str(case), "--paths-only"]) == 1
    output = capsys.readouterr().out
    assert "Overall: mismatch" in output
    prepared = case / "delivery/side-by-side"
    assert (prepared / f"Alteryx/node-{sink}/Alteryx - result.csv").read_bytes() == original.read_bytes()
    python = prepared / f"Python/node-{sink}/Python - result.csv"
    assert python.read_bytes() == (case / "delivery/delivery-output/result.csv").read_bytes()


@pytest.mark.parametrize(("disabled", "emitted", "skip"), [
    (True, False, True), (False, False, False), (False, True, False), (True, True, False),
])
def test_container_entry_distinguishes_empty_capture_from_missing_capture(tmp_path, disabled, emitted, skip):
    from alteryx2python.parity.designer_evidence import _skips

    builder = WorkflowBuilder()
    source = str(builder.add_text_input(["Name"], [["sample"]]))
    target = str(builder.add_filter('[Name] = "eligible"'))
    builder.connect(source, target)
    root = ET.fromstring(builder.render())
    nodes = root.find("Nodes")
    first = nodes.find(f"Node[@ToolID='{target}']")
    nodes.remove(first)
    container = ET.SubElement(nodes, "Node", ToolID="100")
    ET.SubElement(container, "GuiSettings", Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer")
    config = ET.SubElement(ET.SubElement(container, "Properties"), "Configuration")
    ET.SubElement(config, "Disabled", value=str(disabled))
    ET.SubElement(container, "ChildNodes").append(first)
    workflow = tmp_path / "container.yxwz"
    ET.ElementTree(root).write(workflow, encoding="utf-8")
    manifest = {"source": str(workflow), "nodes": [{"node_id": source}, {"node_id": target}]}
    snapshots = {(source, "Output"): {"rows": [[{"kind": "string", "value": "sample"}]]}}
    if emitted:
        snapshots[target, "True"] = {"rows": []}
    skipped, containers = _skips(manifest, snapshots, {source: {"Output"}, target: {"True"}},
                                 {source, target} if emitted else {source}, "success")
    assert (target in skipped) == skip
    if containers:
        assert containers[0]["entry_nodes_with_input"] == [target]


def test_grouped_render_pair_uses_names_even_when_workbooks_differ(tmp_path):
    from openpyxl import Workbook
    from test_migration import dynamic_render_fixture

    from alteryx2python.parity.migration import prepare_migration
    from alteryx2python.parity.output_comparison import build_output_comparison
    from alteryx2python.parity.runner import write_json

    case = tmp_path / "case"
    prepare_migration(dynamic_render_fixture(tmp_path, missing=False), case)
    native = case / "native"
    delivery = case / "delivery"
    output = delivery / "delivery-output"
    output.mkdir(parents=True)
    pairs = {"report-first.xlsx": "Desk A.xlsx", "report-second.xlsx": "Desk B.xlsx"}
    for filename, basename in pairs.items():
        for target, cell in ((native / "render-6" / filename, filename), (output / basename, basename)):
            workbook = Workbook()
            workbook.active["A1"] = cell
            workbook.save(target)
    write_json(delivery / "phase-one-capture.json", {"render_output_names": pairs})

    observed = build_output_comparison(native, delivery)
    assert [row["name"] for row in observed] == list(pairs.values())
    for row, original in zip(observed, pairs):
        assert row["alteryx"].read_bytes() == (native / "render-6" / original).read_bytes()
        assert row["python"].read_bytes() == (output / row["name"]).read_bytes()
