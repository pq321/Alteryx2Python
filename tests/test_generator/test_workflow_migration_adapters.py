import json
import csv
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

from alteryx2python.comparison.workbook import workbook_snapshot
from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.runtime.app_config import apply_actions
from alteryx2python.tools.delivery import render_xlsx_tables
from alteryx2python.tools.unavailable import ToolUnavailableError
from alteryx2python.workflow_generator import WorkflowBuilder


def save_workflow(builder, directory, *, event=False):
    root = ET.fromstring(builder.render())
    if event:
        events = ET.SubElement(root.find("Properties"), "Events")
        ET.SubElement(events, "Event", When="AfterRun", Command="legacy-log.bat")
    path = directory / "demo.yxmd"
    ET.ElementTree(root).write(path, encoding="utf-8")
    return XmlWorkflowParser().parse(path)


@pytest.mark.parametrize("missing", [False, True])
def test_logging_migrates_only_selected_event_in_both_phases(tmp_path, caplog, missing):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["x"], [[2]])
    output = builder.add_csv_output("report.csv")
    builder.connect(source, output)
    workflow = save_workflow(builder, tmp_path, event=True)
    if missing:
        (tmp_path / "report.csv").mkdir()
    with caplog.at_level("INFO", logger="alteryx.workflow"):
        if missing:
            with pytest.raises(OSError):
                run_workflow_graph(workflow, WorkflowContext({"log_event_ids": ["0"]}))
        else:
            run_workflow_graph(workflow, WorkflowContext({"log_event_ids": ["0"]}))
    first = json.loads(caplog.records[-1].message)
    destination = tmp_path / "delivery"
    destination.mkdir()
    if missing:
        (destination / "report.csv").mkdir()
    delivered = tmp_path / "phase_two.py"
    ReadablePythonGenerator().generate(workflow, log_event_ids=["0"]).write(delivered)
    logfile = tmp_path / "workflow.jsonl"
    process = subprocess.run([sys.executable, "-I", str(delivered), "--output-dir", str(destination),
                              "--workflow-log", str(logfile)], capture_output=True)
    assert (process.returncode != 0) == missing, process.stderr
    second = json.loads(logfile.read_text(encoding="utf-8"))
    for entry in (first, second):
        assert entry["status"] == ("failed" if missing else "success")
        assert entry["error_count"] == int(missing)
        assert entry["conversion_error_count"] is None
        assert entry["run_id"] and entry["started_at"] <= entry["finished_at"]
        assert entry["event_id"] == "0"
    assert first["run_id"] != second["run_id"]
    if not missing:
        csv_file = tmp_path / "existing.csv"
        csv_file.write_text("Module,Status,Errors\n", encoding="utf-8")
        columns = tmp_path / "columns.json"
        columns.write_text('["workflow","status","error_count"]', encoding="utf-8")
        subprocess.run([sys.executable, "-I", str(delivered), "--output-dir", str(destination),
                        "--workflow-log", str(csv_file), "--workflow-log-columns", str(columns)], check=True)
        with csv_file.open(encoding="utf-8", newline="") as handle:
            assert list(csv.reader(handle)) == [["Module", "Status", "Errors"], ["demo", "success", "0"]]


@pytest.mark.parametrize("modifier", ["Prepend", "ReplacePath"])
def test_dynamic_input_grouped_workbook_delivery(tmp_path, modifier):
    builder = WorkflowBuilder()
    for filename, region, values in [("a.xlsx", "APAC", [4]), ("b.xlsx", "EMEA", [7, 9])]:
        if modifier == "ReplacePath":
            region = str(tmp_path / "original" / (region + "report.xlsx"))
        pd.DataFrame({"Region": region, "Value": values}).to_excel(tmp_path / filename, index=False)
    paths = builder.add_text_input(["Path"], [["b.xlsx"], ["a.xlsx"], ["b.xlsx"]])
    dynamic = builder._node("DynamicInput", """
        <InputConfiguration><Configuration><File FileFormat="25">a.xlsx|||Sheet1$</File></Configuration></InputConfiguration>
        <Mode>ReadList</Mode><ReadList_Field>Path</ReadList_Field><ReadList_Type>Path</ReadList_Type>
    """, (200, 100))
    table = builder._node("PortfolioComposerTable", """
        <TableMode>Basic</TableMode><GroupingFields><Field name="Region" /></GroupingFields>
        <TableFields><Field name="Value" /></TableFields>
    """, (400, 100))
    layout = builder._node("PortfolioComposerLayout", """
        <GroupingMode>PerGroup</GroupingMode><GroupingFields><Field name="Region" /></GroupingFields>
        <Orientation>V</Orientation><Separator>Continuous</Separator>
        <LayoutFields><Field name="Table" /></LayoutFields>
    """, (500, 100))
    render = builder._node("PortfolioComposerRender", f"""
        <OutputFile>nested/report.xlsx</OutputFile><BatchMode value="True" />
        <GroupField>Region</GroupField><FilenameModifier>{modifier}</FilenameModifier><DataField>Layout</DataField>
    """, (600, 100))
    builder.connect(paths, dynamic)
    builder.connect(dynamic, table)
    builder.connect(table, layout)
    builder.connect(layout, render)
    workflow = save_workflow(builder, tmp_path)
    phase_one = tmp_path / "phase-one"
    run_workflow_graph(workflow, WorkflowContext({"delivery_profile": "xlsx-table-v1", "output_dir": phase_one}))
    phase_two = tmp_path / "phase-two"
    script = tmp_path / "phase_two.py"
    ReadablePythonGenerator().generate(workflow, delivery_profile="xlsx-table-v1").write(script)
    process = subprocess.run([sys.executable, "-I", str(script), "--input-dir", str(tmp_path),
                              "--output-dir", str(phase_two)], capture_output=True)
    assert process.returncode == 0, process.stderr
    assert sorted(path.name for path in phase_two.glob("*.xlsx")) == ["APACreport.xlsx", "EMEAreport.xlsx"]
    for name, expected in {"APAC": [4], "EMEA": [7, 9]}.items():
        filename = name + "report.xlsx"
        first, second = workbook_snapshot(phase_one / filename), workbook_snapshot(phase_two / filename)
        assert list(second) == ["sheet1"]
        assert first == second
        assert pd.read_excel(phase_two / filename)["Value"].tolist() == expected
    assert not (tmp_path / "nested").exists()
    assert not (tmp_path / "original").exists()


def test_dynamic_input_warns_and_grouped_layout_creates_named_worksheets(tmp_path):
    from alteryx2python.workflow_audit import audit_workflow

    with pd.ExcelWriter(tmp_path / 'actual.xlsx', engine='openpyxl') as writer:
        for source_sheet, label, values in [('A', 'Summary', [4]), ('B', 'Detail', [7, 9])]:
            pd.DataFrame({'SheetName': label, 'Value': values}).to_excel(writer, sheet_name=source_sheet, index=False)

    builder = WorkflowBuilder()
    paths = builder.add_text_input(['Config_File_With_Sheet'], [
        ['actual.xlsx|||`B$`'], ['missing.xlsx|||A$'], ['actual.xlsx|||`A$`'], ['actual.xlsx|||Missing$'],
    ])
    dynamic = builder._node('DynamicInput', '''
        <InputConfiguration><Configuration><File FileFormat="25">portable-template.xlsx|||Template$</File></Configuration></InputConfiguration>
        <Mode>ReadList</Mode><ReadList_Field>Config_File_With_Sheet</ReadList_Field><ReadList_Type>Path</ReadList_Type>
        <ErrorBehaviour>Warning</ErrorBehaviour>
    ''', (200, 100))
    table = builder._node('PortfolioComposerTable', '''
        <TableMode>Basic</TableMode><GroupingFields><Field name="SheetName" /></GroupingFields>
        <ShowHeader value="True" /><TableFields><Field name="Value" /></TableFields>
    ''', (300, 100))
    layout = builder._node('PortfolioComposerLayout', '''
        <GroupingMode>PerGroup</GroupingMode><GroupingFields><Field name="SheetName" /></GroupingFields>
        <Orientation>V</Orientation><Separator>Breaking</Separator><SectionNameForGroup>SheetName</SectionNameForGroup>
        <LayoutFields><Field name="Table" selected="True" /></LayoutFields>
    ''', (400, 100))
    render = builder._node('PortfolioComposerRender', '<OutputFile>report.xlsx</OutputFile><DataField>Layout</DataField>', (500, 100))
    for upstream, downstream in zip([paths, dynamic, table, layout], [dynamic, table, layout, render]):
        builder.connect(upstream, downstream)
    workflow = save_workflow(builder, tmp_path)

    first_dir = tmp_path / 'phase-one'
    context = WorkflowContext({'delivery_profile': 'xlsx-table-v1', 'output_dir': first_dir})
    result = run_workflow_graph(workflow, context)
    assert result.node_results[str(dynamic)].outputs['Output']['Value'].tolist() == [4, 7, 9]
    assert len(context.warnings) == 2

    second_dir = tmp_path / 'phase-two'
    script = tmp_path / 'phase_two.py'
    ReadablePythonGenerator().generate(workflow, delivery_profile='xlsx-table-v1').write(script)
    completed = subprocess.run([sys.executable, '-I', str(script), '--input-dir', str(tmp_path),
                                '--output-dir', str(second_dir)], capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert b'missing.xlsx' in completed.stderr and b'Missing$' in completed.stderr
    first = workbook_snapshot(first_dir / 'report.xlsx')
    second = workbook_snapshot(second_dir / 'report.xlsx')
    assert first == second
    assert list(second) == ['Summary', 'Detail']
    assert second['Summary'] == [[('s', 'Value')], [('n', 4)]]
    assert second['Detail'] == [[('s', 'Value')], [('n', 7)], [('n', 9)]]
    audit = audit_workflow(workflow, run=True, delivery_profile='xlsx-table-v1')
    assert audit['execution']['nodes'][-1]['status'] == 'success'
    assert len(audit['execution']['warnings']) == 2
    assert not (tmp_path / 'report.xlsx').exists()


def test_dynamic_input_uses_template_schema_when_all_paths_are_skipped(tmp_path):
    from alteryx2python.tools.dynamicinput import read_file_list

    pd.DataFrame({'Value': [1]}).to_excel(tmp_path / 'template.xlsx', index=False)
    paths = pd.DataFrame({'Path': ['missing.xlsx']})
    warnings = []
    frame = read_file_list(paths, 'Path', 'template.xlsx|||Sheet1$', {'header': 0}, tmp_path, 'warning', warnings.append)
    assert frame.empty and list(frame) == ['Value']
    assert len(warnings) == 1 and 'missing.xlsx' in warnings[0]
    with pytest.raises(FileNotFoundError):
        read_file_list(paths, 'Path', 'template.xlsx|||Sheet1$', {'header': 0}, tmp_path)

    pd.DataFrame({'Other': [9]}).to_excel(tmp_path / 'a-wrong.xlsx', index=False)
    paths = pd.DataFrame({'Path': ['a-wrong.xlsx', 'template.xlsx']})
    data = read_file_list(paths, 'Path', 'template.xlsx|||Sheet1$', {'header': 0}, tmp_path, 'warning', warnings.append)
    assert data['Value'].tolist() == [1]
    assert 'a-wrong.xlsx' in warnings[-1]


def test_native_dynamic_update_cell_binds_question_in_phase_one_and_two(tmp_path):
    root = ET.parse(Path("examples/cli/parameter-app.yxwz")).getroot()
    action = root.find(".//Actions//Action")
    action.clear()
    for key, value in {
        "Type": "Dynamic", "Expression": "{{INPUT}}", "Destination": "1/Data/r[1]/c[1]",
        "Mapping": "Update Cell", "Mode": "Expression",
    }.items():
        ET.SubElement(action, key).text = value
    ET.SubElement(action, "ToolId", value="4")
    for connection in root.findall("./Connections/Connection"):
        if connection.find("Origin").get("ToolID") == "4":
            connection.find("Destination").set("ToolID", "1")
    path = tmp_path / "dynamic.yxwz"
    ET.ElementTree(root).write(path, encoding="utf-8")
    workflow = XmlWorkflowParser().parse(path)
    artifact = ReadablePythonGenerator().generate(workflow)
    namespace = {}
    exec(artifact.verification_source, namespace)
    for answer in (2, 7):
        runtime = run_workflow_graph(workflow, WorkflowContext({"answers": {"factor": answer}}))
        checkpoints = {}
        namespace["run_workflow"](factor=answer, input_dir=tmp_path, output_dir=tmp_path / "delivery", checkpoints=checkpoints)
        assert runtime.node_results["2"].outputs["Output"]["result"].tolist() == [answer * 2, 10]
        pd.testing.assert_frame_equal(runtime.node_results["2"].outputs["Output"], checkpoints["2"]["Output"])
    action.find("Destination").text = "1/File"
    with pytest.raises(ToolUnavailableError, match="unsupported destination: 1/File"):
        apply_actions(root, {"factor": 7})


def test_replacepath_collisions_fail_before_writing(tmp_path):
    frame = pd.DataFrame({"Path": ["C:/one/report.xlsx", "D:/two/REPORT.xlsx"],
                          "Table": ['{"columns":["Value"],"data":[[1]]}'] * 2})
    with pytest.raises(ValueError, match="Duplicate XLSX Render target"):
        render_xlsx_tables(frame, tmp_path / "base.xlsx", "Table", "Path", "ReplacePath")
    assert not list(tmp_path.glob("*.xlsx"))


def test_as_of_replays_date_time_now(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["placeholder"], [[""]])
    sink = builder.add_csv_output("dated.csv")
    builder.connect(source, sink, "DTN")
    root = ET.fromstring(builder.render())
    node = root.find("./Nodes/Node")
    node.find("GuiSettings").set("Plugin", "DateTimeNow")
    node.find("Properties/Configuration").clear()
    ET.SubElement(node.find("Properties/Configuration"), "Value", name="OutputFormat").text = "yyyy-MM-dd"
    macro = r"DateTimeNow\Supporting_Macros\DTNEngine.yxmc"
    node.find("EngineSettings").attrib = {"Macro": macro, "EngineDll": "Macro", "EngineDllEntryPoint": macro}
    path = tmp_path / "date.yxmd"
    ET.ElementTree(root).write(path, encoding="utf-8")
    workflow = XmlWorkflowParser().parse(path)
    run_workflow_graph(workflow, WorkflowContext({"as_of": "2026-10-13"}))
    script = tmp_path / "phase_two.py"
    ReadablePythonGenerator().generate(workflow).write(script)
    subprocess.run([sys.executable, "-I", str(script), "--as-of", "2026-10-13",
                    "--output-dir", str(tmp_path / "delivery")], check=True)
    assert (tmp_path / "dated.csv").read_bytes() == (tmp_path / "delivery" / "dated.csv").read_bytes()
    assert (tmp_path / "dated.csv").read_text().splitlines() == ["DateTimeNow", "2026-10-13"]


def test_formula_date_and_message_use_replay_clock(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["path"], [[r"C:\Inbox\Report.xlsx"]])
    formula = builder.add_formula([
        ("DayKey", "V_WString", "32", 'DateTimeFormat(DateTimeToday(), "%Y%m%d")'),
        ("Name", "V_WString", "32", "FileGetFileName([path])"),
    ])
    message = builder._node("Message", """
        <When>Filter</When><Filter>[DayKey]='20261013'</Filter><Type>Warning</Type>
        <MessageExpression>[Name]</MessageExpression>
    """, (500, 100))
    sink = builder.add_csv_output("dated.csv")
    for left, right in [(source, formula), (formula, message), (message, sink)]:
        builder.connect(left, right)
    workflow = save_workflow(builder, tmp_path)
    context = WorkflowContext({"as_of": "2026-10-13"})
    run_workflow_graph(workflow, context)
    assert context.warnings == ["Report"]
    script = tmp_path / "phase_two.py"
    ReadablePythonGenerator().generate(workflow).write(script)
    process = subprocess.run([sys.executable, "-I", str(script), "--as-of", "2026-10-13",
                              "--output-dir", str(tmp_path / "delivery")], capture_output=True, check=True)
    assert b"RuntimeWarning: Report" in process.stderr
    assert (tmp_path / "dated.csv").read_bytes() == (tmp_path / "delivery" / "dated.csv").read_bytes()


def test_bound_excel_input_and_composite_join_in_both_phases(tmp_path):
    pd.DataFrame({"Key": [1, 1, 2], "Account": ["a", "b", "a"]}).to_excel(
        tmp_path / "local.xlsx", index=False, sheet_name="Data"
    )
    builder = WorkflowBuilder()
    left = builder._node("DbFileInput", '<File FileFormat="25">C:/legacy/original.xlsx|||Data$</File>', (50, 100))
    right = builder.add_text_input(["ID", "Code", "Score"], [[1, "b", 9], [2, "q", 7]])
    join = builder._node("Join", """
        <JoinInfo connection="Left"><Field field="Key" /><Field field="Account" /></JoinInfo>
        <JoinInfo connection="Right"><Field field="ID" /><Field field="Code" /></JoinInfo>
        <SelectConfiguration><Configuration>
        <OrderChanged value="True"/><SelectFields><SelectField field="Right_Score" rename="Score"/>
        <SelectField field="Left_Key" selected="False"/><SelectField field="*Unknown" selected="True"/>
        </SelectFields></Configuration></SelectConfiguration>
    """, (400, 100))
    builder.connect(left, join, target_anchor="Left")
    builder.connect(right, join, target_anchor="Right")
    workflow = save_workflow(builder, tmp_path)
    bindings = {str(left): "local.xlsx"}
    first = run_workflow_graph(workflow, WorkflowContext({"input_bindings": bindings, "input_dir": tmp_path}))
    second = {}
    artifact = ReadablePythonGenerator().generate(workflow, input_bindings=bindings)
    scope = {}
    exec(artifact.verification_source, scope)
    scope["run_workflow"](input_dir=tmp_path, output_dir=tmp_path / "delivery", checkpoints=second)
    for name, frame in first.node_results[str(join)].outputs.items():
        pd.testing.assert_frame_equal(frame, second[str(join)][name])
    assert first.node_results[str(join)].outputs["Join"]["Score"].tolist() == [9]
    with pytest.raises(ValueError, match="changes the configured file format"):
        ReadablePythonGenerator().generate(workflow, input_bindings={str(left): "local.csv"})


def test_deferred_message_error_runs_after_file_sink(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["value"], [[1]])
    message = builder._node("Message", """
        <When>All</When><Type>Error</Type><MessageExpression>"deferred problem"</MessageExpression>
    """, (300, 100))
    sink = builder.add_csv_output("result.csv")
    builder.connect(source, message)
    builder.connect(message, sink)
    workflow = save_workflow(builder, tmp_path)
    with pytest.raises(ValueError, match="deferred problem"):
        run_workflow_graph(workflow, WorkflowContext())
    script = tmp_path / "phase_two.py"
    ReadablePythonGenerator().generate(workflow).write(script)
    result = subprocess.run([sys.executable, "-I", str(script), "--output-dir", str(tmp_path / "delivery")],
                            capture_output=True)
    assert result.returncode != 0
    assert b"deferred problem" in result.stderr
    assert (tmp_path / "result.csv").read_bytes() == (tmp_path / "delivery" / "result.csv").read_bytes()


@pytest.mark.parametrize(('severity', 'cancel', 'missing', 'values'), [
    ('ErrorStop', False, True, [1]),
    ('ErrorStop', False, False, [1, 2, 3]),
    ('ErrorStop', True, True, None),
    ('Error', False, True, [1, 2, 3]),
])
def test_file_exists_message_controls_records_and_workflow(tmp_path, severity, cancel, missing, values):
    from xml.sax.saxutils import escape

    present = tmp_path / 'present.txt'
    candidate = tmp_path / 'candidate.txt'
    present.touch()
    if not missing:
        candidate.touch()
    builder = WorkflowBuilder()
    source = builder.add_text_input(['value', 'path'], [[1, present], [2, candidate], [3, present]])
    message = builder._node('Message', f'<When>Filter</When><Filter>{escape("!FileExists([path])")}</Filter>'
                            f'<Type>{severity}</Type><MessageExpression>"missing file"</MessageExpression>', (300, 100))
    sink = builder.add_csv_output('result.csv')
    builder.connect(source, message)
    builder.connect(message, sink)
    root = ET.fromstring(builder.render())
    ET.SubElement(root.find('Properties'), 'CancelOnError', value=str(cancel))
    path = tmp_path / 'message.yxmd'
    ET.ElementTree(root).write(path, encoding='utf-8')
    workflow = XmlWorkflowParser().parse(path)
    if missing:
        with pytest.raises(ValueError, match='missing file'):
            run_workflow_graph(workflow, WorkflowContext())
    else:
        run_workflow_graph(workflow, WorkflowContext())
    script = tmp_path / 'phase_two.py'
    ReadablePythonGenerator().generate(workflow).write(script)
    delivered = tmp_path / 'delivery'
    result = subprocess.run([sys.executable, '-I', str(script), '--output-dir', str(delivered)], capture_output=True)
    assert (result.returncode != 0) == missing
    if missing:
        assert b'missing file' in result.stderr
    for output in [tmp_path / 'result.csv', delivered / 'result.csv']:
        if values is None:
            assert not output.exists()
        else:
            assert pd.read_csv(output)['value'].tolist() == values
