"""Compare one seven-input Analytic App with an independent Python report."""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from alteryx2python.parity.delivery import capture_generated_phase_one, reusable_arguments
from alteryx2python.parity.migration import launch_designer, prepare_migration, resume_migration
from alteryx2python.parity.runner import file_hash, verify_manifest, write_json
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.app_config import MANUAL_CHOICE_SEPARATOR
from alteryx2python.workflow_generator import WorkflowBuilder

from .app_reference import REPORT_COLUMNS, run_report


CONTROL_SPECS = (
    ("suffix", "TextBox", "TextBox.QuestionTextBox", "Report label suffix", "Reviewed", {}),
    ("include_archived", "BooleanGroup", "CheckBoxGroup.CheckBoxGroup", "Include archived trades", False,
     {"Collapsable": False}),
    ("region", "ListBox", "DropDownListBox.DropDown", "Region", "APAC", {
        "Multiple": False, "Mode": "Manual",
        "Manual_Values": f"Asia Pacific{MANUAL_CHOICE_SEPARATOR}APAC\nEurope{MANUAL_CHOICE_SEPARATOR}EMEA",
    }),
    ("detail", "RadioGroup", "RadioButtonGroup.RadioButtonGroup", "Detailed report", True, {"Collapsable": False}),
    ("summary", "RadioGroup", "RadioButtonGroup.RadioButtonGroup", "Summary report", False, {"Collapsable": False}),
    ("report_date", "Date", "Date.Date", "Report date", "2026-11-18", {}),
    ("report_folder", "FolderBrowse", "FolderBrowse.FolderBrowse", "Report folder", "reports-a", {}),
    ("input_file", "FileBrowse", "FileBrowse.FileBrowse", "Trade CSV", "trades.csv",
     {"SaveAs": False, "Mode": "FileSpec", "FileSpec": "CSV files (*.csv)|*.csv"}),
)

TRADES = "trade_id,region,status,amount\nT001,APAC,posted,120\nT002,APAC,archived,40\nT003,EMEA,posted,90\n"
ALTERNATE_TRADES = "trade_id,region,status,amount\nT009,EMEA,archived,70\nT010,EMEA,posted,100\nT011,APAC,posted,55\n"


def _properties(parent, entries):
    for tag, value in entries.items():
        child = ET.SubElement(parent, tag)
        if isinstance(value, bool):
            child.set("value", str(value))
        else:
            child.text = str(value)


def build_app(path):
    builder = WorkflowBuilder()
    trades = builder._node("DbFileInput", """
        <File FileFormat="0">trades.csv</File>
        <FormatSpecificOptions>
          <HeaderRow>True</HeaderRow><Delimeter>,</Delimeter><CodePage>932</CodePage>
        </FormatSpecificOptions>
    """, (80, 300))
    typed_trades = builder.add_select(
        [(name, "True") for name in ("trade_id", "region", "status", "amount")],
        include_unknown=False, field_types={"amount": ("Int64", 8)}, position=(160, 300),
    )
    columns = ["suffix", "include_archived", "detail", "summary", "requested_date", "report_folder"]
    options = builder.add_text_input(columns, [["Reviewed", "False", "True", "False", "2026-11-18", "reports-a"]],
                                     (80, 400))
    append = builder._node("AppendFields", """
        <CartesianMode>Error</CartesianMode>
        <SelectConfiguration><Configuration outputConnection="Output">
          <OrderChanged value="False"/><CommaDecimal value="False"/>
          <SelectFields><SelectField field="*Unknown" selected="True"/></SelectFields>
        </Configuration></SelectConfiguration>
    """, (220, 300))
    calculated = builder.add_formula([
        ("include_flag", "V_WString", "16", 'IF [include_archived] THEN "TRUE" ELSE "FALSE" ENDIF'),
        ("report_date", "V_WString", "10", 'DateTimeFormat([requested_date], "%Y-%m-%d")'),
        ("label", "V_WString", "100", '[trade_id] + " " + [suffix]'),
        ("display_amount", "Int64", "8", "IF [detail] AND ![summary] THEN [amount] ELSE 0 ENDIF"),
        ("report_path", "V_WString", "1024", 'FileAddPaths([report_folder], "summary.csv")'),
    ], (360, 300))
    eligible = builder.add_filter('([status] = "posted" OR [include_flag] = "TRUE") AND [region] = "REGION_TOKEN"', (500, 300))
    selected = builder.add_select([(name, "True") for name in REPORT_COLUMNS], include_unknown=False, position=(640, 300))
    sink = builder.add_csv_output("report.csv", (780, 300))
    builder.connect(trades, typed_trades)
    builder.connect(typed_trades, append, target_anchor="Targets")
    builder.connect(options, append, target_anchor="Source")
    builder.connect(append, calculated)
    builder.connect(calculated, eligible)
    builder.connect(eligible, selected, source_anchor="True")
    builder.connect(selected, sink)

    root = ET.fromstring(builder.render())
    root.set("yxmdVer", "2025.1")
    nodes, wires = root.find("Nodes"), root.find("Connections")
    runtime = root.find("Properties/RuntimeProperties")
    for tag in ("ModuleType", "Questions", "Actions"):
        old = runtime.find(tag)
        if old is not None:
            runtime.remove(old)
    group = ET.SubElement(ET.SubElement(runtime, "Actions"), "NoCondition")
    tab = ET.SubElement(ET.SubElement(runtime, "Questions"), "Question")
    # Designer's saved app order keeps the editor's Run as Analytic App button visible.
    _properties(runtime, {"ModuleType": "Wizard", "Wiz_ShowOutput": True})
    ET.SubElement(ET.SubElement(runtime, "Wiz_OpenOutputTools"), "Tool", ToolId=str(sink), Selected="True")
    _properties(tab, {"Type": "Tab", "Name": "Questions"})
    ET.SubElement(tab, "ToolId", value="100")
    tab_node = ET.SubElement(nodes, "Node", ToolID="100")
    tab_gui = ET.SubElement(tab_node, "GuiSettings", Plugin="AlteryxGuiToolkit.Questions.Tab.Tab")
    ET.SubElement(tab_gui, "Position", x="0", y="50")
    ET.SubElement(ET.SubElement(tab_node, "Properties"), "Configuration")
    questions = ET.SubElement(tab, "Questions")
    _properties(group, {"Type": "NoCondition", "Description": "(Always Run)"})
    actions = ET.SubElement(group, "True")
    for index, (name, kind, plugin, description, default, extras) in enumerate(CONTROL_SPECS, start=1):
        question_id, action_id = str(100 + index), str(200 + index)
        for current, binding, y in ((question_id, "AlteryxGuiToolkit.Questions." + plugin, 50),
                                    (action_id, "AlteryxGuiToolkit.Action.Action", 155)):
            node = ET.SubElement(nodes, "Node", ToolID=current)
            gui = ET.SubElement(node, "GuiSettings", Plugin=binding)
            ET.SubElement(gui, "Position", x=str(index * 110), y=str(y))
            ET.SubElement(ET.SubElement(node, "Properties"), "Configuration")
        question = ET.SubElement(questions, "Question")
        _properties(question, {"Type": kind, "Description": description, "Name": name, "Default": default, **extras})
        ET.SubElement(question, "ToolId", value=question_id)
        if kind in {"BooleanGroup", "RadioGroup"}:
            ET.SubElement(question, "Questions")
        action = ET.SubElement(actions, "Action")
        ET.SubElement(action, "ToolId", value=action_id)
        if name == "input_file":
            target = trades
            _properties(action, {"Type": "UpdateInput", "Required": True})
            ET.SubElement(action, "InputTool", value=str(target))
            ET.SubElement(question, "InputToolId", value=str(target))
        elif name == "region":
            target = eligible
            _properties(action, {"Type": "UpdateValue", "Mode": "Simple", "Replace": True,
                                 "ReplaceText": "REGION_TOKEN", "Destination": f"{target}/Expression"})
        else:
            target = options
            column = columns.index("requested_date" if name == "report_date" else name) + 1
            _properties(action, {"Type": "UpdateValue", "Mode": "Simple", "Replace": False,
                                 "Destination": f"{target}/Data/r[1]/c[{column}]"})
        for source_id, destination, anchor in ((question_id, action_id, "Question"), (action_id, str(target), "Action")):
            wire = ET.SubElement(wires, "Connection", name="#1" if anchor == "Question" else f"#{index + 1}")
            ET.SubElement(wire, "Origin", ToolID=source_id, Connection=anchor)
            ET.SubElement(wire, "Destination", ToolID=destination, Connection=anchor)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.reader(stream))


def compare_app(directory):
    directory = directory.resolve()
    directory.mkdir(parents=True)
    source = directory / "transaction-app.yxwz"
    build_app(source)
    (directory / "trades.csv").write_text(TRADES, encoding="utf-8")
    (directory / "alternate-trades.csv").write_text(ALTERNATE_TRADES, encoding="utf-8")
    (directory / "reports-a").mkdir()
    (directory / "reports-b").mkdir()
    defaults = {item[0]: item[4] for item in CONTROL_SPECS}
    # A header-only fixture exercises all parameters even when no rows reach the report.
    (directory / "empty-trades.csv").write_text(TRADES.splitlines()[0] + "\n", encoding="utf-8")
    cases = {
        "defaults": defaults,
        "alternate": {**defaults, "suffix": 'Ops "review"', "include_archived": True, "region": "EMEA",
                      "detail": False, "summary": True, "report_date": "2026-12-01", "report_folder": "reports-b",
                      "input_file": "alternate-trades.csv"},
        "empty": {**defaults, "region": "EMEA", "input_file": "empty-trades.csv"},
    }
    reports = []
    shared_script = directory / "defaults/delivery/phase_two.py"
    for label, answers in cases.items():
        case = directory / label
        prepare_migration(source, case, supplied=answers,
                          instrumented_filename=f"{directory.name}-{label}.yxwz")
        delivery = case / "delivery"
        output = delivery / "delivery-output"
        if label == "defaults":
            compiled = resume_migration(case)
            if compiled.get("phase_two_mode") != "reusable" or compiled["phase_one_vs_phase_two"] != "match":
                raise ValueError(f"The app could not produce a verified reusable script: {compiled}")
            contract = json.loads(shared_script.with_suffix(".manifest.json").read_text(encoding="utf-8"))
            output_node, = contract["reusable"]["outputs"]
            phase_two_hash = file_hash(shared_script)
        else:
            manifest = verify_manifest(case / "native")
            workflow = XmlWorkflowParser().parse(Path(manifest["source"]))
            delivery.mkdir()
            captured = capture_generated_phase_one(workflow, delivery, answers=manifest["answers"])
            bindings = delivery / "phase-two-bindings.json"
            write_json(bindings, reusable_arguments(contract, workflow, manifest["answers"], output))
            completed = subprocess.run(
                [sys.executable, "-I", str(shared_script), "--bindings", str(bindings)],
                capture_output=True, timeout=60, check=True,
            )
            (delivery / "standalone.stdout.txt").write_bytes(completed.stdout)
            match = captured["status"] == "success" and captured["sink_artifacts"][output_node] == file_hash(output / "report.csv")
            compiled = {"phase_one_vs_phase_two": "match" if match else "mismatch", "native_vs_phase_one": "incomplete"}
        original = {**answers, "input_file": str(directory / answers["input_file"]),
                    "report_folder": str(directory / answers["report_folder"])}
        run_report(original, case / "handwritten-output")
        expected = _read_csv(case / "handwritten-output/report.csv")
        actual = _read_csv(output / "report.csv")
        reports.append({
            "case": label, "answers": answers, "phase_one_vs_phase_two": compiled["phase_one_vs_phase_two"],
            "handwritten_vs_phase_two": "match" if expected == actual else "mismatch",
            "records": len(actual) - 1, "phase_two_sha256": file_hash(shared_script),
            "native_vs_phase_one": compiled["native_vs_phase_one"],
        })
    matches = all(item["phase_one_vs_phase_two"] == item["handwritten_vs_phase_two"] == "match"
                  and item["phase_two_sha256"] == phase_two_hash for item in reports)
    result = {"status": "match" if matches else "mismatch", "phase_two_script": str(shared_script), "cases": reports}
    write_json(directory / "comparison.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--designer", nargs="?", const="auto", choices=["auto", "wand", "options"])
    parser.add_argument("--designer-pid", type=int)
    args = parser.parse_args()
    report = compare_app(args.directory)
    designer_failed = False
    if args.designer:
        case_path = args.directory.resolve() / "defaults"
        designer = launch_designer(case_path, args.designer, args.designer_pid)
        report["designer"] = designer
        designer_failed = designer["status"] != "outputs_ready"
        if not designer_failed:
            native = resume_migration(case_path, native_outcome="success")
            report["cases"][0]["native_vs_phase_one"] = native["native_vs_phase_one"]
            designer["comparison_report"] = native["report"]
            designer_failed = native["status"] != "match"
        write_json(args.directory / "comparison.json", report)
    print(json.dumps(report, indent=2))
    return int(report["status"] != "match" or designer_failed)


if __name__ == "__main__":
    raise SystemExit(main())
