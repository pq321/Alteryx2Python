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
