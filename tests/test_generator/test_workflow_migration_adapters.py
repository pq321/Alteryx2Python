import json
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


def test_dynamic_input_grouped_workbook_delivery(tmp_path):
    builder = WorkflowBuilder()
    for filename, region, values in [("a.xlsx", "APAC", [4]), ("b.xlsx", "EMEA", [7, 9])]:
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
    render = builder._node("PortfolioComposerRender", """
        <OutputFile>nested/report.xlsx</OutputFile><BatchMode value="True" />
        <GroupField>Region</GroupField><FilenameModifier>Prepend</FilenameModifier><DataField>Table</DataField>
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
