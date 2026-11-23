"""End-to-end regression for branched reconciliation packages."""

from itertools import combinations
import json
from pathlib import Path

import pytest

from alteryx2python.parity import delivery, presentation
from alteryx2python.parity.amp_export import AMP_HEADER, native_probe_path
from alteryx2python.parity.migration import prepare_migration, resume_migration
from alteryx2python.parity.runner import verify_manifest
from alteryx2python.workflow_generator import WorkflowBuilder


@pytest.fixture
def reconciliation(tmp_path):
    builder = WorkflowBuilder()
    paths = builder.add_text_input(["path"], [["trades.csv"]])
    reader = builder._node("DynamicInput", """
        <InputConfiguration><Configuration><File FileFormat="0">template.csv</File>
        <FormatSpecificOptions><CodePage>65001</CodePage></FormatSpecificOptions></Configuration></InputConfiguration>
        <Mode>ReadList</Mode><ReadList_Field>path</ReadList_Field><ReadList_Type>Path</ReadList_Type>
    """, (150, 100))
    builder.connect(paths, reader)
    source = builder.add_text_input(["lookup_id", "rate"], [["1", "1.25"], ["1", "1.5"], ["3", "2.5"]])
    rates = builder.add_formula([("Multiplier", "FixedDecimal", "19.2", "[rate]")])
    builder.connect(source, rates)
    outputs = ("Join", "Left", "Right")
    joins = {}
    for width in (1, 2, 3):
        for anchors in combinations(outputs, width):
            join = builder.add_join("id", "lookup_id")
            joins[anchors] = join
            builder.connect(reader, join, target_anchor="Left")
            builder.connect(rates, join, target_anchor="Right")
            for anchor in anchors:
                sink = builder.add_csv_output(f"{join}-{anchor}.csv")
                builder.connect(join, sink, anchor)
    full_join = joins[outputs]
    amount = builder.add_formula([("Amount", "Double", "8", "[lots] * [price] * [Multiplier]")])
    filter_id = builder.add_filter("[Amount] > 0")
    totals = builder.add_summarize([("id", "GroupBy", "id"), ("Amount", "Sum", "Total")])
    workbook = builder._node("DbFileOutput", '<File FileFormat="25">report.xlsx|||Amounts</File>', (600, 200))
    builder.connect(full_join, amount, "Join")
    builder.connect(amount, filter_id)
    selective = builder.add_select([("id", "True"), ("Amount", "True")], include_unknown=False)
    builder.connect(filter_id, selective, "True")
    builder.connect(selective, totals)
    rejected = builder.add_csv_output("rejected.csv")
    builder.connect(filter_id, rejected, "False")
    builder.connect(totals, workbook)
    trades = "id,lots,price\n" + "".join(
        f"1,{index},0.5\n2,{index + 1},0.75\n" for index in range(1, 101)
    )
    (tmp_path / "trades.csv").write_text(trades, encoding="utf-8")
    (tmp_path / "template.csv").write_text("id,lots,price\n", encoding="utf-8")
    workflow = tmp_path / "reconciliation.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    return workflow, joins


def test_complex_workflow_all_join_anchor_combinations(reconciliation, tmp_path):
    workflow, joins = reconciliation
    case = tmp_path / "case"
    prepare_migration(workflow, case)
    result = resume_migration(case)
    assert result["phase_one_vs_phase_two"] == "match", result
    assert result["native_vs_phase_one"] == "incomplete"
    output = case / "delivery/delivery-output"
    assert (output / "report.xlsx").is_file()
    assert len(list(output.glob("*.csv"))) == 13
    from alteryx2python.cli import main
    from contextlib import redirect_stdout
    from io import StringIO

    (case / "presentation-result.json").write_text(json.dumps({"report": result["report"]}), encoding="utf-8")
    display = StringIO()
    with redirect_stdout(display):
        assert main(["demo", "deliver", "--case", str(case), "--paths-only"]) == 1
    replay = next(line for line in display.getvalue().splitlines() if line.startswith("Replay recorded case:"))
    assert f"--config '{case / 'delivery/case_config.json'}'" in replay
    assert f"--as-of '{result['as_of']}'" in replay
    for anchors, node_id in joins.items():
        for anchor in anchors:
            lines = (output / f"{node_id}-{anchor}.csv").read_text().splitlines()
            assert len(lines) == {"Join": 201, "Left": 101, "Right": 2}[anchor]
            assert lines[1].split(",")[0] == {"Join": "1", "Left": "2", "Right": "3"}[anchor]


def test_complex_workflow_finds_first_swapped_join_anchor(reconciliation, tmp_path, monkeypatch):
    workflow, joins = reconciliation
    case = tmp_path / "case"
    prepare_migration(workflow, case)
    original_generate = delivery.ModularPackageGenerator.generate

    def swap_outputs(generator, *args, **kwargs):
        artifact = original_generate(generator, *args, **kwargs)
        source = artifact.files["pipeline.py"]
        original = "return joined_out, left_out"
        assert original in source
        artifact.files["pipeline.py"] = source.replace(original, "return left_out, joined_out", 1)
        return artifact

    monkeypatch.setattr(delivery.ModularPackageGenerator, "generate", swap_outputs)
    result = resume_migration(case)
    assert result["phase_one_vs_phase_two"] == "mismatch", result
    diff = result["phase_two_first_divergence"]
    assert (diff["node_id"], diff["anchor"]) == (str(joins[("Join", "Left")]), "Join")


def test_amp_timeout_resumes_only_remaining_batches(reconciliation, tmp_path, monkeypatch, capsys):
    workflow, _ = reconciliation
    case = tmp_path / "case"
    prepare_migration(workflow, case)
    native = case / "native"
    manifest = verify_manifest(native)
    probes = [native / item["file"] for item in manifest["probes"]]
    assert len(probes) > 16
    for path in probes:
        path.write_bytes(AMP_HEADER + b"fixture")
    launched = []
    attempts = []

    def launch(plan, report, mode, pid, launcher, *, log, timeout):
        assert timeout == 600
        folder = Path(json.loads(plan.read_text())[0]["run_dir"])
        names = [item["file"] for item in json.loads((folder / "manifest.json").read_text())["probes"]]
        attempts.append(names)
        if len(attempts) == 2:
            return {"status": "output_timeout"}
        for name in names:
            (folder / name).write_bytes(b"classic fixture")
        launched.extend(names)
        return {"status": "outputs_ready"}

    monkeypatch.setattr(presentation, "launch_designer_plan", launch)
    from alteryx2python.cli import main

    assert main(["demo", "compare", "--case", str(case), "--outcome", "success"]) == 1
    result = json.loads((case / "delivery/acceptance.json").read_text(encoding="utf-8"))
    assert "output_timeout" in result["amp_export_issue"]
    assert result["native_vs_phase_one"] == "incomplete"
    assert result["phase_one_vs_phase_two"] == "match"
    assert "AMP export evidence incomplete" in (case / "delivery/comparison-summary.md").read_text(encoding="utf-8")
    assert "Exporting AMP probes" in capsys.readouterr().err
    presentation._export_amp_probes(case, manifest, {}, set())
    assert len(launched) == len(set(launched)) == len(probes)
    assert attempts[1] == attempts[2]
    assert all(native_probe_path(path).is_file() for path in probes)
    assert presentation._export_amp_probes(case, manifest, {}, set()) is None


def test_message_reports_null_and_non_null_path_in_both_phases(tmp_path):
    import subprocess
    import sys

    from alteryx2python.generator.package_compiler import ModularPackageGenerator
    from alteryx2python.parser.xml_parser import XmlWorkflowParser
    from alteryx2python.runtime.context import WorkflowContext, WorkflowMessageError
    from alteryx2python.runtime.executor import run_workflow_graph

    for index, value in enumerate(("", "bad.csv")):
        directory = tmp_path / str(index)
        directory.mkdir()
        builder = WorkflowBuilder()
        source = builder.add_text_input(["Path"], [[value]])
        message = builder._node("Message", """
            <When>First</When><Type>Error</Type>
            <MessageExpression>"Missing file: " + [Path]</MessageExpression>
        """, (200, 100))
        builder.connect(source, message)
        path = directory / "message.yxmd"
        path.write_text(builder.render(), encoding="utf-8")
        workflow = XmlWorkflowParser().parse(path)
        with pytest.raises(WorkflowMessageError, match="Missing file: " + value):
            run_workflow_graph(workflow, WorkflowContext())
        artifact = ModularPackageGenerator().generate(workflow)
        package = directory / "package"
        artifact.write(package)
        run = subprocess.run([sys.executable, "-I", str(package)], capture_output=True, encoding="utf-8")
        assert run.returncode == 1
        assert "Missing file: " + value in run.stderr
        assert "TypeError" not in run.stderr


def test_declared_datetime_coarse_comparison_preserves_timestamp_precision():
    from alteryx2python.parity.behavior import _compare_checkpoint

    def snapshot(kind, value):
        return {
            "columns": ["dt_now"], "schema": [{"name": "dt_now", "type": "DateTime"}],
            "rows": [[{"kind": kind, "value": value}]],
        }

    expected = snapshot("datetime", "2026-11-23T15:14:57")
    actual = snapshot("string", "2026-11-23 15:14:57")
    options = ("83", "Formula", "outputs", True, (set(), {}))
    result = _compare_checkpoint(expected, actual, *options)
    assert result["status"] == "coarse_match"
    assert result["exact_comparison"]["status"] == "mismatch"
    for different in ("2026-11-23 15:14:58", "2026-11-23 15:14:57.1", "2026-11-23 15:14:57+09:00"):
        assert _compare_checkpoint(expected, snapshot("string", different), *options)["status"] == "mismatch"
