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
    render = builder._node("PortfolioComposerRender", f"""
        <OutputFile>nested/report.xlsx</OutputFile><BatchMode value="True" />
        <GroupField>Region</GroupField><FilenameModifier>{modifier}</FilenameModifier><DataField>Table</DataField>
    """, (600, 100))
    builder.connect(paths, dynamic)
    builder.connect(dynamic, table)
    builder.connect(table, render)
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
