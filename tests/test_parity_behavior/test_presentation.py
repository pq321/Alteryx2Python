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
    assert (case / "phase-two-candidate/pipeline.py").is_file()

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


@pytest.mark.parametrize("native_probe_value", ["sample", "Different"])
def test_demo_compares_without_prompt_and_presents_both_outputs_on_mismatch(
    tmp_path, monkeypatch, capsys, native_probe_value,
):
    import pandas as pd

    from alteryx2python.parity import delivery, designer_evidence, migration, presentation, runner
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
    path.write_text(json.dumps(frame_snapshot(pd.DataFrame({"Name": [native_probe_value]}))), encoding="utf-8")
    for module in (runner, designer_evidence):
        monkeypatch.setattr(module, "read_yxdb", lambda filename: json.loads(filename.read_text(encoding="utf-8")))
    original = case / "native" / manifest["sink_files"][str(sink)]
    original.write_bytes(b"Name\r\nDifferent\r\n")
    runner.write_json(case / "designer-run.json", [
        {"status": "outputs_ready", "workflow": launch["native_workflow"]},
    ])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    validations = []

    def verify(directory):
        validations.append(directory)
        return runner.verify_manifest(directory)

    for module in (presentation, migration, delivery):
        monkeypatch.setattr(module, "verify_manifest", verify)
    assert main(["demo", "compare", "--case", str(case)]) == 1
    assert validations == [case / "native"]
    acceptance = json.loads((case / "delivery/acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["timings_seconds"].keys() >= {
        "amp_probe_export", "phase_one_capture", "native_collection", "checkpoint_comparison_and_reports",
        "phase_two_compile_run_and_checks", "step_three_total",
    }
    summary = capsys.readouterr().out
    assert len(summary.strip().splitlines()) == 3
    count = int(native_probe_value != "sample")
    assert f"{count} anchor mismatches, 0 incomplete anchors, 1 output differences." in summary
    report = case / "delivery/comparison-summary.md"
    assert f"Comparison report: {report}" in summary
    details = report.read_text(encoding="utf-8")
    header = details.split("## Nodes to review", 1)[0].strip().splitlines()
    assert header == [
        "# Step 3 comparison", "",
        "| Comparison | Status | Mismatches |",
        "| --- | --- | ---: |",
        f"| [Designer / Phase 1](native-vs-phase-one.json) | mismatch | {count + 1} |",
        "| [Phase 1 / Phase 2](phase-one-vs-phase-two.json) | match | 0 |",
    ]
    assert "[Designer run and skipped nodes](../native/designer-evidence.json)" in details
    assert "[Independent Phase 2 run](standalone.json)" in details
    phase_one = next((case / "delivery/phase-one-output").glob(f"python-sink-*-{sink}.csv"))
    row = next(line for line in details.splitlines() if f"| Alteryx Tool ID {sink} (DbFileOutput) |" in line)
    assert "| output file mismatch | — |" in row
    assert "Side-by-side comparison (HTML)" in details
    if not count:
        assert "| — | [Input context](tables/" in row
    assert f"| [result.csv](../native/{original.name}) | [result.csv](phase-one-output/{phase_one.name}) |" in row
    findings = json.loads((case / "delivery/native-vs-phase-one.json").read_text(encoding="utf-8"))
    if count:
        input_check = next(item for item in findings["comparisons"] if item["direction"] == "inputs")
        assert input_check["status"] == "mismatch"
        assert input_check["duplicates_upstream"] == {"node_id": str(source), "anchor": "Output"}
        assert f"| Alteryx Tool ID {source} (TextInput) | output mismatch |" in details
        assert "input mismatch" not in details
    assert findings["artifact_differences"] == [{
        "group": "sink_artifacts", "key": str(sink), "node_id": str(sink),
        "status": "different", "filename": "result.csv", "designer_file": original.name,
        "phase_one_file": phase_one.name,
    }]
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


@pytest.mark.parametrize(("columns", "rows", "dimension"), [
    (["Qty", "Prod"], [[1, "00123"]] * 99 + [[2, "ABC"]], "columns"),
    (["Prod", "Qty"], [["00123", 1]], "row_count"),
    (["Prod", "Qty"], [[123, 1]] * 99 + [["ABC", 2]], "cell"),
])
def test_demo_compare_keeps_row_details_in_json(tmp_path, monkeypatch, capsys, columns, rows, dimension):
    import re

    import pandas as pd
    from alteryx2python.parity import designer_evidence, runner
    from alteryx2python.parity.migration import prepare_migration
    from alteryx2python.parity.snapshot import frame_snapshot

    builder = WorkflowBuilder(next_tool_id=234)
    node = builder.add_text_input(["Prod", "Qty"], [["00123", 1]] * 99 + [["ABC", 2]])
    workflow = tmp_path / "sample.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    case = tmp_path / "case"
    launch = prepare_migration(workflow, case)
    manifest = runner.verify_manifest(case / "native")
    probe, = manifest["probes"]
    runner.write_json(case / "native" / probe["file"], frame_snapshot(pd.DataFrame(rows, columns=columns, dtype=object)))
    for module in (runner, designer_evidence):
        monkeypatch.setattr(module, "read_yxdb", lambda path: json.loads(path.read_text(encoding="utf-8")))
    runner.write_json(case / "designer-run.json", [
        {"status": "outputs_ready", "workflow": launch["native_workflow"]},
    ])

    assert main(["demo", "compare", str(node), "--anchor", "Output", "--case", str(case)]) == 1

    summary = capsys.readouterr().out
    assert len(summary.strip().splitlines()) == 3
    assert ("0 anchor mismatches" if dimension == "columns" else "1 anchor mismatches") in summary
    report = case / "delivery/comparison-summary.md"
    assert f"Comparison report: {report}" in summary
    details = report.read_text(encoding="utf-8")
    assert "| Alteryx Tool ID |" in details or dimension == "columns"
    node_lines = [line for line in details.splitlines() if f"Alteryx Tool ID {node} (TextInput)" in line]
    if dimension == "columns":
        assert not node_lines
        assert "Output / Output" not in details
    else:
        row, = node_lines
        assert row.startswith(f"| **Alteryx Tool ID {node} (TextInput)** | output mismatch |")
        view = re.search(r"\| \*\*Output / Output\*\* \| \[Output / Output\]\(tables/(node234-anchor1\.html)\)", row)
        assert view and (report.parent / "tables" / view[1]).is_file()
        assert f"Alteryx Tool ID {node} (TextInput)" in (report.parent / "tables" / view[1]).read_text(encoding="utf-8")
        assert f"[Output / Output](../native/{probe['file']})" in row
        assert probe["file"] == "node234-anchor1.yxdb"
        link = re.search(r"\[Output / Output\]\(phase-one-capture\.json#L(\d+)\)", row)
        assert link
        capture = (report.parent / "phase-one-capture.json").read_text(encoding="utf-8").splitlines()
        assert capture[int(link[1]) - 1] == '        "Output": {'
    assert all(value not in details for value in ("Prod", "Qty", "00123", "row 1"))
    assert "[Designer / Phase 1](native-vs-phase-one.json)" in details
    findings = json.loads((case / "delivery/native-vs-phase-one.json").read_text(encoding="utf-8"))
    comparison, = findings["comparisons"]
    if dimension == "columns":
        assert comparison["status"] == "match"
        assert comparison["order_differences"] == ["columns"]
    elif dimension == "row_count":
        assert (comparison["expected_row_count"], comparison["actual_row_count"]) == (1, 100)
    else:
        assert len(comparison["value_differences"]) == 20
        assert comparison["value_differences"][0] == {
            "row": 0, "column": "Prod", "expected": {"kind": "int", "value": "123"},
            "actual": {"kind": "string", "value": "00123"},
        }


def test_demo_coarse_matches_are_available_outside_unmatched_anchors(tmp_path, monkeypatch, capsys):
    from datetime import date

    import pandas as pd
    from alteryx2python.parity import designer_evidence, runner
    from alteryx2python.parity.migration import prepare_migration
    from alteryx2python.parity.snapshot import frame_snapshot

    builder = WorkflowBuilder(next_tool_id=37)
    builder.add_text_input(["Dt"], [["2026-10-13"]])
    workflow = tmp_path / "sample.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    case = tmp_path / "case"
    launch = prepare_migration(workflow, case)
    manifest = runner.verify_manifest(case / "native")
    probe, = manifest["probes"]
    frame = pd.DataFrame({"Dt": [date(2026, 10, 13)]}, dtype=object)
    frame.attrs["alteryx_schema"] = [{"name": "Dt", "type": "Date", "size": 10, "scale": None}]
    runner.write_json(case / "native" / probe["file"], frame_snapshot(frame))
    for module in (runner, designer_evidence):
        monkeypatch.setattr(module, "read_yxdb", lambda path: json.loads(path.read_text(encoding="utf-8")))
    runner.write_json(case / "designer-run.json", [{"status": "outputs_ready", "workflow": launch["native_workflow"]}])

    assert main(["demo", "compare", "--case", str(case)]) == 1
    summary = capsys.readouterr().out
    assert "0 anchor mismatches" in summary and "1 coarse match." in summary
    report = case / "delivery" / "comparison-summary.md"
    details = report.read_text(encoding="utf-8")
    assert "| coarse_match | 0 |" in details
    assert "No node-level findings." in details
    assert "<details><summary>Coarse matches (1 anchor)</summary>" in details
    assert "| Alteryx Tool ID 37 (TextInput) | Output / Output | [Open](tables/node37-anchor1.html) |" in details
    assert (report.parent / "tables" / "node37-anchor1.html").is_file()


def test_workbook_detail_locates_first_different_cell(tmp_path):
    from openpyxl import Workbook
    from alteryx2python.parity.delivery import _workbook_detail

    paths = [tmp_path / name for name in ("designer.xlsx", "python.xlsx")]
    for path, quantity in zip(paths, [25, 27]):
        workbook = Workbook()
        workbook.active.title = "Compare_F"
        workbook.active["C2"] = quantity
        workbook.save(path)

    assert _workbook_detail(*paths) == {
        "dimension": "cell", "sheet": "Compare_F", "cell": "C2",
        "expected": {"type": "n", "value": "25"}, "actual": {"type": "n", "value": "27"},
    }


@pytest.mark.parametrize("false_probe_present", [True, False])
def test_demo_lists_only_unmatched_output_anchors(tmp_path, monkeypatch, capsys, false_probe_present):
    import pandas as pd
    import re

    from alteryx2python.parity import designer_evidence, runner
    from alteryx2python.parity.migration import prepare_migration
    from alteryx2python.parity.snapshot import frame_snapshot

    builder = WorkflowBuilder()
    source = builder.add_text_input(["Name"], [["keep"], ["drop"]])
    node = builder.add_filter('[Name] = "keep"')
    builder.connect(source, node)
    workflow = tmp_path / "branch.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    case = tmp_path / "case"
    launch = prepare_migration(workflow, case)
    manifest = runner.verify_manifest(case / "native")
    captures = {"Output": ["keep", "drop"], "True": ["different"], "False": ["drop"]}
    assert {probe["anchor"] for probe in manifest["probes"] if probe["node_id"] == str(node)} == {"True", "False"}
    for probe in manifest["probes"]:
        anchor = probe["anchor"]
        if false_probe_present or anchor != "False":
            runner.write_json(case / "native" / probe["file"], frame_snapshot(pd.DataFrame({"Name": captures[anchor]})))
    for module in (runner, designer_evidence):
        monkeypatch.setattr(module, "read_yxdb", lambda path: json.loads(path.read_text(encoding="utf-8")))
    runner.write_json(case / "designer-run.json", [{"status": "outputs_ready", "workflow": launch["native_workflow"]}])

    assert main(["demo", "compare", "--case", str(case)]) == 1
    lines = (case / "delivery/comparison-summary.md").read_text(encoding="utf-8").splitlines()
    row, = [line for line in lines if f"| Alteryx Tool ID {node} (Filter) |" in line]
    assert f"| Output / True | [Output / True](tables/node{node}-anchor2.html)" in row
    assert "Output / False" not in row
    assert ("incomplete evidence" in row) == (not false_probe_present)
    parity = json.loads((case / "delivery/native-vs-phase-one.json").read_text(encoding="utf-8"))
    sibling, = [item for item in parity["comparisons"] if item["node_id"] == str(node)
                and item["direction"] == "outputs" and item["anchor"] == "False"]
    expected = "match" if false_probe_present else "incomplete"
    assert sibling["status"] == expected
    assert "1 anchor mismatches" in capsys.readouterr().out


def test_comparison_report_links_encode_paths_and_omit_missing_side(tmp_path):
    from alteryx2python.parity.presentation import _comparison_links

    native = tmp_path / "native"
    delivery = tmp_path / "delivery"
    output = delivery / "phase-one-output/render"
    native.mkdir()
    output.mkdir(parents=True)
    name = "Quarter #1 [Asia] | Results.xlsx"
    (output / "Quarter #1 [Asia].xlsx").touch()

    designer, python = _comparison_links(native, delivery, [], [{
        "node_id": "82", "filename": name, "designer_file": "missing.xlsx",
        "phase_one_file": "render/Quarter #1 [Asia].xlsx",
    }])

    assert designer == {}
    assert python["82"] == [
        r"[Quarter #1 \[Asia\] \| Results.xlsx](phase-one-output/render/Quarter%20%231%20%5BAsia%5D.xlsx)",
    ]


def test_summary_counts_distinct_failures_and_marks_missing_evidence():
    from alteryx2python.parity.presentation import _mismatch_total

    assert _mismatch_total("mismatch", [{"node_id": "9"}], [{"node_id": "9", "filename": "out.csv"}]) == 1
    assert _mismatch_total("mismatch", [], [{"filename": "a.csv"}, {"filename": "b.csv"}]) == 2
    assert _mismatch_total("mismatch", []) == 1
    assert _mismatch_total("incomplete", []) == "—"
    assert _mismatch_total("match", []) == 0
