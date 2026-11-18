import json
from xml.etree import ElementTree as ET

import pytest

from alteryx2python.parity.migration import prepare_migration, prompt_answers, resume_migration
from alteryx2python.parity.runner import file_hash, verify_manifest
from alteryx2python.runtime.app_config import list_questions
from alteryx2python.workflow_events import workflow_events
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


def declare_config_path(root, value):
    properties = root.find("Properties")
    constant = ET.SubElement(ET.SubElement(properties, "Constants"), "Constant")
    ET.SubElement(constant, "Namespace").text = "User"
    ET.SubElement(constant, "Name").text = "FILE_PATH_CONFIG"
    ET.SubElement(constant, "Value").text = str(value)
    ET.SubElement(constant, "IsNumeric", value="False")


def constant_input_fixture(tmp_path, extension, value, variable="FILE_PATH_CONFIG"):
    builder = WorkflowBuilder()
    input_id = builder._node(
        "DbFileInput",
        f'<File FileFormat="0">%User.{variable}%</File>'
        '<FormatSpecificOptions><HeaderRow>True</HeaderRow><Delimeter>,</Delimeter>'
        '<CodePage>932</CodePage></FormatSpecificOptions>',
        (100, 100),
    )
    builder.connect(input_id, builder.add_csv_output("report.csv"))
    root = ET.fromstring(builder.render())
    root.set("yxmdVer", "2025.1")
    if extension == "yxwz":
        ET.SubElement(root.find("Properties/RuntimeProperties"), "ModuleType").text = "Wizard"
    declare_config_path(root, value)
    source = tmp_path / f"variable-input.{extension}"
    ET.ElementTree(root).write(source, encoding="utf-8", xml_declaration=True)
    return source, str(input_id)


@pytest.mark.parametrize("extension, absolute", [("yxmd", False), ("yxwz", True)])
def test_migration_freezes_user_constant_input_before_designer_and_python(tmp_path, extension, absolute):
    config = tmp_path / "file path config.csv"
    config.write_bytes(b"region\r\nAPAC\r\n")
    source, input_id = constant_input_fixture(tmp_path, extension, config if absolute else config.name)
    source_hash = file_hash(source)
    directory = tmp_path / "case"

    receipt = prepare_migration(source, directory)
    assert receipt["status"] == "awaiting_designer"
    assert (directory / "designer-plan.json").is_file()
    snapshot, = json.loads((directory / "inputs.json").read_text(encoding="utf-8"))
    assert snapshot["source"] == str(config.resolve())
    assert verify_manifest(directory / "native")["inputs_sha256"] == {snapshot["snapshot"]: file_hash(config)}
    file_selector = f".//Node[@ToolID='{input_id}']/Properties/Configuration/File"
    assert ET.parse(receipt["native_workflow"]).findtext(file_selector) == snapshot["snapshot"]
    assert ET.parse(source).findtext(file_selector) == "%User.FILE_PATH_CONFIG%"
    assert file_hash(source) == source_hash

    config.write_bytes(b"region\r\nEMEA\r\n")
    result = resume_migration(directory)
    assert result["phase_one_outcome"] == "success"
    assert result["phase_one_vs_phase_two"] == result["standalone_execution"] == "match"
    assert (directory / "delivery/delivery-output/report.csv").read_bytes() == b"region\r\nAPAC\r\n"


def test_migration_freezes_file_browse_answer_using_user_constant(tmp_path):
    source = app_fixture(tmp_path)
    config = tmp_path / "selected.csv"
    config.write_text("amount\n25\n", encoding="utf-8")
    tree = ET.parse(source)
    declare_config_path(tree.getroot(), config)
    tree.write(source, encoding="utf-8", xml_declaration=True)
    directory = tmp_path / "case"

    prepare_migration(source, directory, supplied={"source_file": "%User.FILE_PATH_CONFIG%"})
    manifest = verify_manifest(directory / "native")
    answer = manifest["answers"]["source_file"]
    assert answer.endswith("selected.csv")
    assert manifest["inputs_sha256"][answer] == file_hash(config)
    assert resume_migration(directory)["phase_one_vs_phase_two"] == "match"


def test_migration_identifies_missing_user_constant_at_input_node(tmp_path):
    source, input_id = constant_input_fixture(tmp_path, "yxwz", "unused.csv", variable="UNKNOWN_CONFIG")
    directory = tmp_path / "case"
    with pytest.raises(ValueError, match=rf"Input Data {input_id}: Unresolved workflow variable: User\.UNKNOWN_CONFIG"):
        prepare_migration(source, directory)
    assert not (directory / "designer-plan.json").exists()


@pytest.mark.parametrize("missing", [False, True])
def test_migrate_replaces_selected_after_run_event_for_both_python_phases(tmp_path, missing):
    source = app_fixture(tmp_path)
    tree = ET.parse(source)
    events = ET.SubElement(tree.find("Properties"), "Events")
    ET.SubElement(events, "Event", When="Disabled", Command="disabled.bat")
    ET.SubElement(events, "Event", When="AfterRun", Command="AlteryxLogTest.bat")
    tree.write(source, encoding="utf-8", xml_declaration=True)
    directory = tmp_path / "case"
    answers = {"source_file": "missing.csv"} if missing else None

    receipt = prepare_migration(source, directory, supplied=answers, allow_missing=missing, log_event_ids=["1"])
    manifest = verify_manifest(directory / "native")
    assert receipt["log_event_ids"] == manifest["log_event_ids"] == ["1"]
    assert manifest["event_commands_sha256"] == {}
    assert workflow_events(source.read_text(encoding="utf-8"))[0]["program"] == "AlteryxLogTest.bat"
    instrumented = directory / "native" / manifest["instrumented_file"]
    assert not workflow_events(instrumented.read_text(encoding="utf-8"))
    assert ET.parse(instrumented).find("./Properties/Events/Event").get("Command") == "disabled.bat"

    result = resume_migration(directory)
    evidence = result["logging_events"]
    assert evidence["status"] == result["phase_one_vs_phase_two"] == result["standalone_execution"] == "match"
    assert result["native_vs_phase_one"] == "incomplete"
    for name in ("phase_one_log", "phase_two_log"):
        records = (directory / "delivery" / evidence[name]).read_text(encoding="utf-8").splitlines()
        record, = map(json.loads, records)
        assert record["event_id"] == "1"
        assert record["status"] == ("failed" if missing else "success")
        assert record["error_count"] == int(missing)


def test_migrate_logging_selection_preserves_block_on_unisolated_commands(tmp_path):
    source = app_fixture(tmp_path)
    tree = ET.parse(source)
    events = ET.SubElement(tree.find("Properties"), "Events")
    ET.SubElement(events, "Event", When="BeforeRun", Command="other.bat")
    ET.SubElement(events, "Event", When="AfterRun", Command="AlteryxLogTest.bat")
    tree.write(source, encoding="utf-8", xml_declaration=True)
    with pytest.raises(ValueError, match="enabled After Run"):
        prepare_migration(source, tmp_path / "wrong-event", log_event_ids=["0"])
    with pytest.raises(ValueError, match="needs an isolated workflow event test case"):
        prepare_migration(source, tmp_path / "unisolated", log_event_ids=["1"])
    assert not (tmp_path / "unisolated/designer-plan.json").exists()


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
