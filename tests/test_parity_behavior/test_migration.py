import json
from xml.etree import ElementTree as ET

import pytest

from alteryx2python.parity.migration import prepare_migration, prompt_answers, resume_migration
from alteryx2python.parity.runner import file_hash, verify_manifest
from alteryx2python.runtime.app_config import list_questions
from alteryx2python.workflow_generator import WorkflowBuilder


def app_fixture(tmp_path):
    builder = WorkflowBuilder()
    input_id = builder._node("DbFileInput", '<File FileFormat="0">default.csv</File>', (100, 100))
    formula = builder.add_formula([("report_date", "V_WString", "10", '"DATE_TOKEN"')])
    sink = builder.add_csv_output("dated-output/report.csv")
    builder.connect(input_id, formula)
    builder.connect(formula, sink)
    root = ET.fromstring(builder.render())
    runtime = root.find("Properties/RuntimeProperties")
    if runtime is None:
        runtime = ET.SubElement(root.find("Properties"), "RuntimeProperties")
    module_type = runtime.find("ModuleType")
    if module_type is None:
        module_type = ET.SubElement(runtime, "ModuleType")
    module_type.text = "Wizard"
    for tag in ("Questions", "Actions"):
        old = runtime.find(tag)
        if old is not None:
            runtime.remove(old)
    runtime.append(ET.fromstring("""
        <Questions><Question><Type>Tab</Type><Name>Questions</Name><Questions>
          <Question><Type>Date</Type><Name>report_date</Name><Default>2026-11-18</Default></Question>
          <Question><Type>FileBrowse</Type><Name>source_file</Name><Default>default.csv</Default></Question>
        </Questions></Question></Questions>
    """))
    runtime.append(ET.fromstring(f"""
        <Actions><NoCondition><True>
          <Action><Type>UpdateInput</Type><Variable>source_file</Variable><InputTool value="{input_id}"/></Action>
          <Action><Type>UpdateValue</Type><Variable>report_date</Variable><Replace value="True"/>
            <ReplaceText>DATE_TOKEN</ReplaceText><Destination>{formula}/FormulaFields/FormulaField/@expression</Destination>
          </Action>
        </True></NoCondition></Actions>
    """))
    source = tmp_path / "fixture.yxwz"
    ET.ElementTree(root).write(source, encoding="utf-8", xml_declaration=True)
    (tmp_path / "default.csv").write_text("amount\n5\n", encoding="utf-8")
    return source


@pytest.mark.parametrize("missing", [False, True])
def test_migration_reuses_question_answers_and_compares_standalone_artifacts(tmp_path, missing):
    source = app_fixture(tmp_path)
    selected = tmp_path / "selected.csv"
    if not missing:
        selected.write_text("amount\n25\n", encoding="utf-8")
    responses = iter(["20261117", "2026-11-17", selected.name])
    messages = []
    answers = prompt_answers(list_questions(source), read=lambda _: next(responses), display=messages.append)
    assert "Use YYYY-MM-DD" in messages
    directory = tmp_path / "case"
    source_hash = file_hash(source)
    receipt = prepare_migration(source, directory, supplied=answers, allow_missing=missing)
    assert receipt["status"] == "awaiting_designer"
    manifest = verify_manifest(directory / "native")
    saved = json.loads((directory / "answers.json").read_text(encoding="utf-8"))
    assert saved == manifest["answers"]
    assert saved["report_date"] == "2026-11-17"
    assert manifest["inputs_sha256"][saved["source_file"]] == (None if missing else file_hash(selected))
    assert not (directory / "native/python.json").exists()
    if not missing:
        selected.unlink()
    result = resume_migration(directory)
    assert result["native_vs_phase_one"] == "incomplete"
    assert result["phase_one_vs_phase_two"] == "match"
    assert result["phase_one_outcome"] == ("failed" if missing else "success")
    assert file_hash(source) == source_hash
    assert not (directory / "delivery/phase-two-verification-output").exists()
    if not missing:
        assert (directory / "delivery/delivery-output/report.csv").read_bytes() == b"amount,report_date\r\n25,2026-11-17\r\n"
        assert not (tmp_path / "dated-output").exists()


def test_case_detects_changed_snapshot(tmp_path):
    source = app_fixture(tmp_path)
    directory = tmp_path / "case"
    prepare_migration(source, directory)
    snapshot = next((directory / "inputs").rglob("*.csv"))
    snapshot.write_text("amount\n99\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Input file changed"):
        resume_migration(directory)


def test_app_action_cannot_overwrite_prepared_native_sink(tmp_path):
    source = app_fixture(tmp_path)
    tree = ET.parse(source)
    root = tree.getroot()
    output = next(node for node in root.iter("Node") if node.find("Properties/Configuration/MultiFile") is not None)
    target = output.find("Properties/Configuration/File").text
    runtime = root.find("Properties/RuntimeProperties")
    question = ET.SubElement(runtime.find("Questions/Question/Questions"), "Question")
    ET.SubElement(question, "Type").text = "TextBox"
    ET.SubElement(question, "Name").text = "same_path"
    ET.SubElement(question, "Default").text = target
    action = ET.SubElement(runtime.find("Actions/NoCondition/True"), "Action")
    ET.SubElement(action, "Type").text = "UpdateValue"
    ET.SubElement(action, "Variable").text = "same_path"
    ET.SubElement(action, "Destination").text = f"{output.get('ToolID')}/File"
    tree.write(source, encoding="utf-8", xml_declaration=True)
    with pytest.raises(ValueError, match="overrides the isolated output"):
        prepare_migration(source, tmp_path / "case")
    assert not (tmp_path / "case/designer-plan.json").exists()
