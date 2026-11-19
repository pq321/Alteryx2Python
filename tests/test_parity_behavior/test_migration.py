import json
import runpy
import subprocess
import sys
from datetime import datetime
from xml.etree import ElementTree as ET

from openpyxl import Workbook
import pytest

from alteryx2python.comparison.workbook import workbook_snapshot
from alteryx2python.parity.delivery import capture_generated_phase_one
from alteryx2python.parity.migration import prepare_migration, prompt_answers, resume_migration
from alteryx2python.parity.runner import file_hash, sink_digest, verify_manifest
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.app_config import list_questions
from alteryx2python.workflow_events import workflow_events
from alteryx2python.workflow_generator import WorkflowBuilder


def test_local_formula_compatibility_reaches_both_generated_phases(tmp_path):
    import pandas as pd

    builder = WorkflowBuilder()
    source = builder.add_text_input(["Name"], [["APAC"]])
    formula = builder.add_formula([
        ("path", "V_WString", "100", r"""'C:\Reports\' + LowerCase([Name])"""),
        ("signed", "Int64", "8", "2 * -(3 + 4)"),
        ("compact", "DateTime", "19", """DateTimeParse("20261013", "%Y%m%d")"""),
        ("formatted", "DateTime", "19", """DateTimeParse("2026-10- 3 08:09:10", "%Y-%m-%e %T")"""),
    ])
    builder.connect(source, formula)
    builder.connect(formula, builder.add_csv_output("result.csv"))
    workflow = tmp_path / "formula.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    case = tmp_path / "case"
    prepare_migration(workflow, case)
    result = resume_migration(case)
    assert result["phase_one_vs_phase_two"] == result["standalone_execution"] == "match", result
    row = pd.read_csv(case / "delivery/delivery-output/result.csv").iloc[0]
    assert row["path"] == r"C:\Reports\apac"
    assert row["signed"] == -14
    assert row["compact"] == "2026-10-13 00:00:00"
    assert row["formatted"] == "2026-10-03 08:09:10"


def test_stripping_tracing_preserves_empty_class_syntax():
    import ast

    from alteryx2python.generator.source_linker import RemoveTracing

    tree = ast.parse("class Marker:\n    context.record_node(name)\n")
    transformed = RemoveTracing().visit(tree)
    assert isinstance(transformed.body[0].body[0], ast.Pass)
    compile(ast.fix_missing_locations(transformed), "<generated>", "exec")


def test_amp_excel_copy_preserves_sheet_selection_and_cell_values(tmp_path):
    workbook = Workbook()
    workbook.active.append(["Wrong worksheet"])
    sheet = workbook.create_sheet("R5300")
    sheet.append(["Label", "Amount", "Date", "Identifier"])
    sheet.append(["NA", 1, datetime(2026, 10, 13), "00123"])
    sheet.append([None, None, None, None])
    sheet.append(["", 3, None, "N/A"])
    source_file = tmp_path / "R5300.xlsx"
    workbook.save(source_file)
    source_hash = file_hash(source_file)

    builder = WorkflowBuilder()
    input_id = builder._node("DbFileInput", """
        <File FileFormat="25">R5300.xlsx|||'R5300$'</File>
        <FormatSpecificOptions><HeaderRow>True</HeaderRow></FormatSpecificOptions>
    """, (100, 100))
    output_id = builder._node("DbFileOutput", """
        <File FileFormat="25" MaxRecords="">out/R5300.xlsx|||Target</File>
        <FormatSpecificOptions>
            <MipTenantId /><PreserveFormat>False</PreserveFormat><MipSensitivity />
            <UNCLocal>False</UNCLocal><SkipFieldNames>False</SkipFieldNames>
            <SuppressBlankFile>False</SuppressBlankFile><OutputOption>RemoveFile</OutputOption>
        </FormatSpecificOptions>
        <MultiFile value="False" />
    """, (300, 100))
    builder.connect(input_id, output_id)
    disabled_sink = builder.add_csv_output("out/disabled.csv")
    builder.connect(input_id, disabled_sink)
    root = ET.fromstring(builder.render())
    nodes = root.find("Nodes")
    disabled_node = nodes.find(f"Node[@ToolID='{disabled_sink}']")
    nodes.remove(disabled_node)
    container = ET.SubElement(nodes, "Node", ToolID="100")
    ET.SubElement(container, "GuiSettings", Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer")
    config = ET.SubElement(ET.SubElement(container, "Properties"), "Configuration")
    ET.SubElement(config, "Disabled", value="True")
    ET.SubElement(container, "ChildNodes").append(disabled_node)
    ET.SubElement(root.find("Properties"), "RunWithE2", value="True")
    source = tmp_path / "excel-copy.yxmd"
    ET.ElementTree(root).write(source, encoding="utf-8")

    case = tmp_path / "case"
    prepare_migration(source, case)
    manifest = verify_manifest(case / "native")
    assert manifest["sink_files"] == {str(output_id): f"native-sink-{output_id}.xlsx"}
    assert ET.parse(case / "native" / manifest["instrumented_file"]).find(
        f".//Node[@ToolID='{output_id}']/Properties/Configuration/File"
    ).text.endswith("|||Target")

    result = resume_migration(case)
    assert result["phase_one_outcome"] == "success"
    assert result["phase_one_vs_phase_two"] == "match", result
    assert result["standalone_execution"] == "match"
    assert result["phase_two_mode"] == "reusable"
    delivery_manifest = json.loads((case / "delivery/phase_two.manifest.json").read_text(encoding="utf-8"))
    assert delivery_manifest["reusable"]["omitted_nodes"] == ["100", str(disabled_sink)]
    actual = case / "delivery/delivery-output/R5300.xlsx"
    assert workbook_snapshot(actual) == {
        "Target": [
            [("s", "Label"), ("s", "Amount"), ("s", "Date"), ("s", "Identifier")],
            [("s", "NA"), ("n", 1), ("d", datetime(2026, 10, 13)), ("s", "00123")],
            [(None, None)] * 4,
            [(None, None), ("n", 3), (None, None), ("s", "N/A")],
        ],
    }
    assert not (tmp_path / "out").exists()
    assert file_hash(source_file) == source_hash

    script = case / "delivery/phase_two.py"
    script_hash = file_hash(script)
    code = script.read_text(encoding="utf-8")
    assert 'R5300.xlsx' not in code and 'inputs/1/' not in code
    transform = runpy.run_path(str(script))["transform"]
    import pandas as pd

    supplied = pd.DataFrame({"example": [15]})
    pd.testing.assert_frame_equal(transform(load_data=supplied), supplied)

    alternate = tmp_path / "second-batch"
    alternate.mkdir()
    sheet.append(["second batch", 4, None, "00543"])
    second_input = alternate / "Renamed source.xlsx"
    workbook.save(second_input)
    alternate_source = alternate / "second.yxmd"
    root.find(f".//Node[@ToolID='{input_id}']/Properties/Configuration/File").text = "Renamed source.xlsx|||'R5300$'"
    ET.ElementTree(root).write(alternate_source, encoding="utf-8")
    phase_one = capture_generated_phase_one(XmlWorkflowParser().parse(alternate_source), alternate)
    reused_output = alternate / "replayed/Renamed result.xlsx"
    completed = subprocess.run(
        [sys.executable, "-I", str(script), f"--input-file-{input_id}", str(second_input),
         f"--output-file-{output_id}", str(reused_output)],
        cwd=alternate, capture_output=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert phase_one["status"] == "success"
    assert sink_digest(reused_output) == phase_one["sink_artifacts"][str(output_id)]
    assert file_hash(script) == script_hash


def test_excel_sink_comparison_ignores_sparse_cell_padding_but_preserves_types(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "00123"
    sheet["A3"] = "NA"
    first, second = tmp_path / "first.xlsx", tmp_path / "second.xlsx"
    workbook.save(first)
    sheet["C2"].number_format = "0"
    workbook.save(second)
    assert file_hash(first) != file_hash(second)
    assert sink_digest(first) == sink_digest(second)

    sheet["A1"] = 123
    workbook.save(second)
    assert sink_digest(first) != sink_digest(second)


def dynamic_render_fixture(directory, *, missing=True, excel=False):
    from openpyxl import Workbook

    if excel:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Prod mapping"
        sheet.append(["SheetName", "Value"])
        sheet.append(["Summary", "Alpha"])
        sheet.append(["Detail", "Beta"])
        workbook.save(directory / "source.xlsx")
        source_file, missing_file, file_format = "source.xlsx|||Prod mapping", "missing.xlsx|||Prod mapping", 25
    else:
        (directory / "source.csv").write_text("SheetName,Value\nSummary,Alpha\nDetail,Beta\n", encoding="utf-8")
        source_file, missing_file, file_format = "source.csv", "missing.csv", 0
    builder = WorkflowBuilder()
    source_paths = [[source_file], [missing_file]] if missing else [[source_file]]
    paths = builder.add_text_input(["InputPath"], source_paths)
    dynamic = builder._node("DynamicInput", f"""
        <InputConfiguration><Configuration><Passwords />
          <File FileFormat="{file_format}" OutputFileName="" RecordLimit="" SearchSubDirs="False">template-{source_file}</File>
          <FormatSpecificOptions><HeaderRow>True</HeaderRow><Delimeter>,</Delimeter></FormatSpecificOptions>
        </Configuration></InputConfiguration>
        <Mode>ReadList</Mode><ReadList_Field>InputPath</ReadList_Field><ReadList_Type>Path</ReadList_Type>
        <ErrorBehaviour>Warning</ErrorBehaviour>
    """, (200, 100))
    table = builder._node("PortfolioComposerTable", """
        <TableMode>Basic</TableMode><GroupingFields><Field name="SheetName" /></GroupingFields>
        <ShowHeader value="True" /><Width>432</Width>
        <TableFields><Field name="Value" selected="True" Alignment="Left" /></TableFields>
    """, (300, 100))
    layout = builder._node("PortfolioComposerLayout", """
        <GroupingMode>PerGroup</GroupingMode><GroupingFields><Field name="SheetName" /></GroupingFields>
        <Orientation>V</Orientation><Separator>Breaking</Separator><Width>100%</Width>
        <SectionNameForGroup>SheetName</SectionNameForGroup>
        <LayoutFields orderChanged="True"><Field name="Table" selected="True" Alignment="Center" /></LayoutFields>
    """, (400, 100))
    formula = builder.add_formula([
        ("OutputPath", "V_WString", "1024",
         '"../outside/report-" + DateTimeFormat(DateTimeNow(), "%Y%m%d%H%M%S") + ".xlsx"'),
    ])
    render = builder._node("PortfolioComposerRender", """
        <TempFileType /><OutputFile>temp.xlsx</OutputFile><BatchMode value="True" />
        <GroupField>OutputPath</GroupField><FilenameModifier>ReplacePath</FilenameModifier><DataField>Layout</DataField>
        <Separator>Continuous</Separator><ShowHeader value="False" /><ShowFooter value="False" />
        <PortraitMode value="True" /><PaperType Width="612" Height="792" Left="36" Right="36" Top="36" Bottom="36" />
    """, (600, 100))
    sequence = [paths, dynamic, table, layout, formula, render]
    for upstream, downstream in zip(sequence, sequence[1:]):
        builder.connect(upstream, downstream)
    workflow = directory / "dynamic-render.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    return workflow


@pytest.mark.parametrize("excel", [False, True])
def test_dynamic_input_and_grouped_render_migration(tmp_path, excel):
    from alteryx2python.comparison.workbook import workbook_snapshot
    from alteryx2python.parity.local_adapters import workbook_artifacts
    from alteryx2python.parity.runner import collect_native

    source = dynamic_render_fixture(tmp_path, excel=excel)
    original = file_hash(source)
    case = tmp_path / "case"
    prepare_migration(source, case)
    native = case / "native"
    manifest = verify_manifest(native)
    assert list(manifest["dynamic_inputs"]) == ["2"]
    assert manifest["render_folders"] == {"6": "render-6"}
    assert "5" in manifest["report_projection_nodes"]
    reference = ET.parse(native / manifest["instrumented_file"])
    template = reference.find(".//InputConfiguration/Configuration/File")
    filename = "source.xlsx" if excel else "source.csv"
    snapshot = next((case / "inputs").rglob(filename))
    assert template.text == snapshot.as_posix() + ("|||Prod mapping" if excel else "")
    expression = reference.find(".//FormulaField[@field='OutputPath']").get("expression")
    assert f'DateTimeParse("{manifest["as_of"]}"' in expression
    assert "DateTimeNow()" in (case / source.name).read_text(encoding="utf-8")
    assert len(manifest["inputs_sha256"]) == 2
    assert any(digest is None for digest in manifest["inputs_sha256"].values())
    (tmp_path / filename).unlink()
    assert collect_native(native, manual=True)["render_digests"] is None
    result = resume_migration(case)
    assert result["native_vs_phase_one"] == "incomplete"
    assert result["phase_one_vs_phase_two"] == "match", result
    assert result["phase_two_mode"] == "specialized"
    assert "DynamicInput" in result["phase_two_reuse_blocker"]
    outputs = case / "delivery/delivery-output"
    filename = f'report-{datetime.fromisoformat(manifest["as_of"]):%Y%m%d%H%M%S}.xlsx'
    assert list(workbook_artifacts(outputs)) == [filename]
    workbook = workbook_snapshot(outputs / filename)
    assert list(workbook) == ["Detail", "Summary"]
    assert workbook == {
        "Detail": [[("s", "Value")], [("s", "Beta")]],
        "Summary": [[("s", "Value")], [("s", "Alpha")]],
    }
    assert not (tmp_path / "outside").exists()
    assert file_hash(source) == original



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


def test_inspect_preflights_external_user_input_using_staging_paths(tmp_path, capsys):
    from alteryx2python.cli import main
    from alteryx2python.parser.xml_parser import XmlWorkflowParser
    from alteryx2python.workflow_audit import audit_workflow

    original = tmp_path / "workflow"
    original.mkdir()
    csv = tmp_path / "business config.csv"
    source, input_id = constant_input_fixture(original, "yxwz", csv)
    digest = file_hash(source)
    raw = audit_workflow(XmlWorkflowParser().parse(source), parameter_mode="specialized")
    assert raw["phase_two"]["status"] == "blocked"
    assert "portable binding" in raw["phase_two"]["issues"][0]["reason"]

    inspection = tmp_path / "inspect"
    assert main(["inspect", str(source), "--summary", "--output-dir", str(inspection)]) == 0
    assert "Phase 2 compile: compiled" in capsys.readouterr().out
    audit = json.loads((inspection / "audit.json").read_text(encoding="utf-8"))
    assert audit["phase_two"] == {"status": "compiled", "staged_input_nodes": [input_id]}
    assert audit["execution"]["status"] == "not_requested"
    assert not csv.exists()
    assert file_hash(source) == digest

    csv.write_text("region\nAPAC\n", encoding="utf-8")
    case = tmp_path / "case"
    prepare_migration(source, case)
    final_audit = json.loads((case / "audit.json").read_text(encoding="utf-8"))
    assert final_audit["phase_two"] == {"status": "compiled"}


def test_inspect_and_migrate_distinguish_user_input_runtime_files_and_templates(tmp_path, capsys):
    from pathlib import Path

    from alteryx2python.cli import main

    workflow = dynamic_render_fixture(tmp_path, missing=False)
    config = tmp_path / "file path config.csv"
    config.write_text("InputPath\nsource.csv\n", encoding="utf-8")
    template = tmp_path / "template-source.csv"
    template.write_text("SheetName,Value\nTemplate,Design-time only\n", encoding="utf-8")
    tree = ET.parse(workflow)
    source_node = tree.find(".//Node[@ToolID='1']")
    input_workflow, input_id = constant_input_fixture(tmp_path, "yxmd", config)
    input_node = ET.parse(input_workflow).find(f".//Node[@ToolID='{input_id}']")
    for tag in ("GuiSettings", "Properties", "EngineSettings"):
        source_node.remove(source_node.find(tag))
        source_node.append(input_node.find(tag))
    declare_config_path(tree.getroot(), config)
    tree.write(workflow, encoding="utf-8", xml_declaration=True)

    inspection = tmp_path / "inspection"
    main(["inspect", str(workflow), "--summary", "--output-dir", str(inspection)])
    stdout = capsys.readouterr().out
    inspected = json.loads((inspection / "inspect.json").read_text(encoding="utf-8"))
    assert f"Dependency: {config}" in stdout
    assert str(template) not in stdout
    assert inspected["external_dependencies"] == [str(config)]
    assert inspected["input_paths"] == [
        {"node_id": "1", "configured": "%User.FILE_PATH_CONFIG%", "source": str(config)},
    ]
    assert inspected["dynamic_inputs"] == [
        {"node_id": "2", "path_field": "InputPath", "configured_template": template.name},
    ]

    case = tmp_path / "case"
    prepare_migration(workflow, case)
    snapshots = json.loads((case / "inputs.json").read_text(encoding="utf-8"))
    assert {item["source"] for item in snapshots} == {str(config), str(tmp_path / "source.csv")}
    for item in snapshots:
        assert Path(item["snapshot"]).read_bytes() == Path(item["source"]).read_bytes()
    native = case / "native"
    manifest = verify_manifest(native)
    staged_template = manifest["dynamic_inputs"]["2"]["template"]
    assert staged_template["source"] == str(template)
    assert Path(staged_template["snapshot"]).is_relative_to(case / "templates")
    assert any(Path(path) == Path(staged_template["snapshot"]) for path in manifest["inputs_sha256"])


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
