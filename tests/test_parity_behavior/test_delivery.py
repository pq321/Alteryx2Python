import json
import subprocess

from alteryx2python.expressions.errors import UnsupportedExpressionError
from alteryx2python.parity import delivery as delivery_module
from alteryx2python.parity.delivery import verify_delivery
from alteryx2python.parity.runner import prepare
from alteryx2python.workflow_generator import WorkflowBuilder


def test_generated_delivery_preserves_date_csv_without_claiming_unobserved_native_match(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["JoinDate"], [["2014-12-21"]])
    csv = builder.add_csv_output("records.csv")
    builder.connect(source, csv)
    workflow = tmp_path / "dates.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    native = tmp_path / "native"
    prepare(workflow, native)

    delivery = tmp_path / "delivery"
    result = verify_delivery(native, delivery)

    assert result["status"] == "incomplete"
    assert result["native_vs_phase_one"] == "incomplete"
    assert result["phase_one_vs_phase_two"] == "match"
    assert result["standalone_execution"] == "match"
    assert (delivery / "delivery-output" / "records.csv").read_bytes() == b"JoinDate\r\n2014-12-21\r\n"


def test_phase_two_candidate_survives_phase_one_capture_timeout(tmp_path, monkeypatch):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["Value"], [["example"]])
    builder.connect(source, builder.add_csv_output("records.csv"))
    workflow = tmp_path / "example.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    native = tmp_path / "native"
    prepare(workflow, native)
    destination = tmp_path / "delivery"

    def time_out(*args, **kwargs):
        assert (destination / "package/pipeline.py").is_file()
        raise subprocess.TimeoutExpired("phase one", 1)

    monkeypatch.setattr(delivery_module, "capture_python", time_out)
    result = verify_delivery(native, destination)

    assert result["status"] == "incomplete"
    assert result["phase_two_generation"] == "generated"
    assert result["phase_one_failure"]["type"] == "TimeoutExpired"
    assert result["phase_one_vs_phase_two"] == "pending"
    assert result["native_vs_phase_one"] == "blocked"
    assert not (destination / "standalone.json").exists()
    manifest = json.loads((destination / "package/manifest.json").read_text(encoding="utf-8"))
    assert manifest["phase_one_sha256"] == result["phase_one_sha256"]
    assert manifest["python_differential"] == "unverified"


def test_phase_two_compile_failure_preserves_phase_one_evidence(tmp_path, monkeypatch):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["Value"], [["example"]])
    builder.connect(source, builder.add_csv_output("records.csv"))
    workflow = tmp_path / "example.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    native = tmp_path / "native"
    prepare(workflow, native)

    def unsupported(*args, **kwargs):
        raise UnsupportedExpressionError("Unsupported expression in Phase 2")

    monkeypatch.setattr(delivery_module.ModularPackageGenerator, "generate", unsupported)
    destination = tmp_path / "delivery"
    result = verify_delivery(native, destination)

    assert result["status"] == "blocked"
    assert result["phase_two_generation"] == "failed"
    assert result["failure"]["type"] == "UnsupportedExpressionError"
    assert result["phase_one_outcome"] == "success"
    assert (destination / "native-vs-phase-one.json").is_file()
    assert not (destination / "package").exists()


def test_delivery_attributes_a_standalone_error_to_the_failing_formula(tmp_path, monkeypatch, capsys):
    from alteryx2python.cli import main

    builder = WorkflowBuilder()
    source = builder.add_text_input(["Value"], [["7"]])
    formula = builder.add_formula([("Amount", "Double", "8", "[Value] * 2")])
    builder.connect(source, formula)
    builder.connect(formula, builder.add_csv_output("records.csv"))
    workflow = tmp_path / "example.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    case = tmp_path / "case"
    native = case / "native"
    prepare(workflow, native)
    real_generate = delivery_module.ModularPackageGenerator.generate

    def inject_failure(generator, workflow, **kwargs):
        artifact = real_generate(generator, workflow, **kwargs)
        original = artifact.files["pipeline.py"]
        header = "def compute_amount(df: pd.DataFrame) -> pd.DataFrame:\n"
        assert header in original
        artifact.files["pipeline.py"] = original.replace(
            header, header + '    raise TypeError("Exercise Phase 2 failure reporting")\n', 1,
        )
        return artifact

    monkeypatch.setattr(delivery_module.ModularPackageGenerator, "generate", inject_failure)
    destination = case / "delivery"
    result = verify_delivery(native, destination)

    assert result["phase_one_outcome"] == "success"
    assert result["phase_one_vs_phase_two"] == "mismatch"
    failure = result["phase_two_stage_failure"]
    assert failure["node_id"] == str(formula)
    assert failure["type"] == "TypeError"
    assert "raise TypeError" in (destination / "package/pipeline.py").read_text(encoding="utf-8").splitlines()[failure["line"] - 1]
    report = json.loads((destination / "phase-one-vs-phase-two.json").read_text(encoding="utf-8"))
    assert report["phase_two_stage_failure"] == failure

    receipt = {"report": str(destination / "acceptance.json"), "node": "999"}
    (case / "presentation-result.json").write_text(json.dumps(receipt), encoding="utf-8")
    assert main(["demo", "deliver", "--case", str(case), "--paths-only"]) == 1
    assert f'pipeline.py:{failure["line"]} (node {formula})' in capsys.readouterr().out
