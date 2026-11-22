"""Tests for config-decoupled native Python package compilation (Child 2)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

from alteryx2python.generator.package_compiler import ModularPackageGenerator
from alteryx2python.parity.runner import capture_python
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.workflow_generator import WorkflowBuilder


def _read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def test_seven_question_app_compiles_once_and_runs_all_configs_without_recompilation(tmp_path: Path):
    from examples.python_pipeline_comparison.app_reference import run_report
    from examples.python_pipeline_comparison.compare_app import ALTERNATE_TRADES, CONTROL_SPECS, TRADES, build_app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    app_path = data_dir / "transaction-app.yxwz"
    build_app(app_path)
    (data_dir / "trades.csv").write_text(TRADES, encoding="utf-8")
    (data_dir / "alternate-trades.csv").write_text(ALTERNATE_TRADES, encoding="utf-8")
    (data_dir / "empty-trades.csv").write_text(TRADES.splitlines()[0] + "\n", encoding="utf-8")
    (data_dir / "reports-a").mkdir()
    (data_dir / "reports-b").mkdir()

    workflow = XmlWorkflowParser().parse(app_path)
    artifact = ModularPackageGenerator().generate(workflow)

    pipeline_py = artifact.files["pipeline.py"]
    config_toml = artifact.files["config.toml"]

    # 1. Verify pipeline.py is concise, modular, native Pandas, and free of input injection / Alteryx baggage
    assert "alteryx_schema" not in pipeline_py
    assert "declare_field" not in pipeline_py
    assert "bounded_text" not in pipeline_py
    assert "nullable_integer" not in pipeline_py
    assert "trades.csv" not in pipeline_py
    assert "'APAC'" not in pipeline_py
    assert "'Reviewed'" not in pipeline_py
    assert "to_dict('records')" not in pipeline_py
    assert len(pipeline_py.splitlines()) <= 70
    # Simple app has no reusable macros or multi-row reference tables -> adaptive layout omits them
    assert not any(k.startswith(("macros/", "references/")) for k in artifact.files)
    assert "[inputs.trades]" in config_toml
    assert "[outputs.report]" in config_toml
    assert 'region = "APAC"' in config_toml

    pkg_dir = tmp_path / "tx_report_pkg"
    artifact.write(pkg_dir)

    defaults = {item[0]: item[4] for item in CONTROL_SPECS}
    cases = {
        "defaults": defaults,
        "alternate": {
            **defaults,
            "suffix": 'Ops "review"',
            "include_archived": True,
            "region": "EMEA",
            "detail": False,
            "summary": True,
            "report_date": "2026-12-01",
            "report_folder": "reports-b",
            "input_file": "alternate-trades.csv",
        },
        "empty": {
            **defaults,
            "region": "EMEA",
            "input_file": "empty-trades.csv",
        },
    }

    # 2. Run ALL THREE cases against the SINGLE compiled Python package by swapping config JSON only!
    for case_name, ans in cases.items():
        expected_dir = tmp_path / f"expected_{case_name}"
        actual_dir = tmp_path / f"actual_{case_name}"
        full_ans = {
            **ans,
            "input_file": str(data_dir / ans["input_file"]),
            "report_folder": str(data_dir / ans["report_folder"]),
        }
        run_report(full_ans, expected_dir)

        case_cfg = tmp_path / f"{case_name}.json"
        case_cfg.write_text(
            json.dumps({
                "parameters": {
                    **ans,
                    "report_folder": str(data_dir / ans["report_folder"]),
                }
            }),
            encoding="utf-8",
        )

        # Test package directory execution (`python -I <pkg_dir>`) on defaults and direct `cli.py` on others
        cmd = (
            [sys.executable, "-I", str(pkg_dir)]
            if case_name == "defaults"
            else [sys.executable, "-I", str(pkg_dir / "cli.py")]
        )
        proc = subprocess.run(
            [*cmd, "--config", str(case_cfg), "--input-dir", str(data_dir), "--output-dir", str(actual_dir)],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert _read_csv(actual_dir / "report.csv") == _read_csv(expected_dir / "report.csv")


def test_multirow_reference_table_and_user_variable_and_summarize_sort(tmp_path: Path):
    xml = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput"><Position x="50" y="50"/></GuiSettings>
      <Properties>
        <Configuration>
          <NumRows value="3"/>
          <Fields><Field name="desk"/><Field name="lots"/></Fields>
          <Data>
            <r><c>EMEA</c><c>4</c></r>
            <r><c>APAC</c><c>2</c></r>
            <r><c>APAC</c><c>3</c></r>
          </Data>
        </Configuration>
        <Annotation><Name>desk_trades</Name></Annotation>
      </Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"><Position x="160" y="50"/></GuiSettings>
      <Properties><Configuration><FormulaFields>
        <FormulaField expression="[lots] * [%User.unit_fee%]" field="fee" size="8" type="Int64"/>
      </FormulaFields></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxFormula"/>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxSpatialPluginsGui.Summarize.Summarize"><Position x="260" y="50"/></GuiSettings>
      <Properties><Configuration><SummarizeFields>
        <SummarizeField field="desk" action="GroupBy" rename="desk"/>
        <SummarizeField field="fee" action="Sum" rename="total_fee"/>
      </SummarizeFields></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxSpatialPluginsEngine.dll" EngineDllEntryPoint="AlteryxSummarize"/>
    </Node>
    <Node ToolID="4">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Sort.Sort"><Position x="360" y="50"/></GuiSettings>
      <Properties><Configuration><SortInfo locale="1033"><Field field="desk" order="Ascending"/></SortInfo></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxSort"/>
    </Node>
    <Node ToolID="5">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput"><Position x="460" y="50"/></GuiSettings>
      <Properties><Configuration>
        <File FileFormat="0">fees.csv</File>
        <FormatSpecificOptions><HeaderRow>True</HeaderRow><Delimeter>,</Delimeter><CodePage>65001</CodePage></FormatSpecificOptions>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxDbFileOutput"/>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
    <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
    <Connection><Origin ToolID="3" Connection="Output"/><Destination ToolID="4" Connection="Input"/></Connection>
    <Connection><Origin ToolID="4" Connection="Output"/><Destination ToolID="5" Connection="Input"/></Connection>
  </Connections>
  <Properties>
    <Constants>
      <Constant><Namespace>User</Namespace><Name>unit_fee</Name><Value>10</Value><IsNumeric value="True"/></Constant>
    </Constants>
    <RuntimeProperties/>
  </Properties>
</AlteryxDocument>
"""
    wf_path = tmp_path / "fees.yxmd"
    wf_path.write_text(xml, encoding="utf-8")
    workflow = XmlWorkflowParser().parse(wf_path)

    artifact = ModularPackageGenerator().generate(workflow)
    assert "references/desk_trades.csv" in artifact.files
    # Multi-row TextInput is externalized to CSV, NOT hardcoded as DataFrame literal in pipeline.py!
    assert "EMEA" not in artifact.files["pipeline.py"]
    assert "user_unit_fee = 10" in artifact.files["config.toml"]
    # Summarize + Sort grouped into one cohesive stage function
    assert "def summarize_by_desk(" in artifact.files["pipeline.py"]

    pkg_dir = tmp_path / "fees_pkg"
    artifact.write(pkg_dir)

    out_default = tmp_path / "out_10"
    out_override = tmp_path / "out_25"
    p1 = subprocess.run(
        [sys.executable, "-I", str(pkg_dir / "cli.py"), "--output-dir", str(out_default)],
        capture_output=True, text=True, check=False,
    )
    assert p1.returncode == 0, p1.stderr
    assert _read_csv(out_default / "fees.csv") == [["desk", "total_fee"], ["APAC", "50"], ["EMEA", "40"]]

    # Override User.unit_fee via --set without touching Python code!
    p2 = subprocess.run(
        [sys.executable, "-I", str(pkg_dir / "cli.py"), "--set", "user_unit_fee=25", "--output-dir", str(out_override)],
        capture_output=True, text=True, check=False,
    )
    assert p2.returncode == 0, p2.stderr
    assert _read_csv(out_override / "fees.csv") == [["desk", "total_fee"], ["APAC", "125"], ["EMEA", "100"]]


def test_reusable_and_iterative_macros_execute_standalone_and_match_phase1(tmp_path: Path):
    macro = tmp_path / "bump.yxmc"
    macro.write_text(
        """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration><Name>Input</Name></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"><Position x="150" y="50"/></GuiSettings>
      <Properties><Configuration><FormulaFields>
        <FormulaField expression="[v] + 5" field="v" size="8" type="Int64"/>
      </FormulaFields></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxFormula"/>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput"><Position x="250" y="50"/></GuiSettings>
      <Properties><Configuration><Name>Output</Name></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroOutput"/>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
    <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
  </Connections>
  <Properties><RuntimeProperties/></Properties>
</AlteryxDocument>
""",
        encoding="utf-8",
    )

    caller = tmp_path / "caller.yxmd"
    caller.write_text(
        f"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration>
        <NumRows value="2"/><Fields><Field name="v"/></Fields><Data><r><c>1</c></r><r><c>10</c></r></Data>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings><Position x="150" y="50"/></GuiSettings>
      <Properties><Configuration/></Properties>
      <EngineSettings Macro="{macro.name}"/>
    </Node>
    <Node ToolID="3">
      <GuiSettings><Position x="250" y="50"/></GuiSettings>
      <Properties><Configuration/></Properties>
      <EngineSettings Macro="{macro.name}"/>
    </Node>
    <Node ToolID="4">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput"><Position x="350" y="50"/></GuiSettings>
      <Properties><Configuration>
        <File FileFormat="0">bumped.csv</File>
        <FormatSpecificOptions><HeaderRow>True</HeaderRow><Delimeter>,</Delimeter><CodePage>65001</CodePage></FormatSpecificOptions>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxDbFileOutput"/>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
    <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
    <Connection><Origin ToolID="3" Connection="Output"/><Destination ToolID="4" Connection="Input"/></Connection>
  </Connections>
  <Properties><RuntimeProperties/></Properties>
</AlteryxDocument>
""",
        encoding="utf-8",
    )
    workflow = XmlWorkflowParser().parse(caller)
    artifact = ModularPackageGenerator().generate(workflow)
    assert "macros/bump.py" in artifact.files
    assert artifact.files["pipeline.py"].count("run_bump(") == 2

    pkg_dir = tmp_path / "macro_pkg"
    out_dir = tmp_path / "macro_out"
    artifact.write(pkg_dir)
    proc = subprocess.run(
        [sys.executable, "-I", str(pkg_dir / "cli.py"), "--output-dir", str(out_dir)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert _read_csv(out_dir / "bumped.csv") == [["v"], ["11"], ["20"]]


def test_option_a_auto_refinement_triggers_only_when_data_hits_truncation(tmp_path: Path):
    # Workflow with narrow V_WString(3) Select where actual data "ABCDEF" exceeds width 3
    builder = WorkflowBuilder()
    (tmp_path / "raw.csv").write_text("code,region\nABCDEF,APAC\nXYZ,EMEA\n", encoding="utf-8")
    inp = builder._node(
        "DbFileInput",
        '<File FileFormat="0">raw.csv</File><FormatSpecificOptions><HeaderRow>True</HeaderRow><Delimeter>,</Delimeter><CodePage>65001</CodePage></FormatSpecificOptions>',
        (50, 50),
    )
    sel = builder.add_select(
        [("code", "True"), ("region", "True")],
        include_unknown=False,
        field_types={"code": ("V_WString", 3), "region": ("V_WString", 10)},
    )
    flt = builder.add_filter('[region] = "APAC"')
    out = builder.add_csv_output("matched.csv")
    builder.connect(inp, sel)
    builder.connect(sel, flt)
    builder.connect(flt, out, source_anchor="True")

    wf_path = tmp_path / "quirks.yxmd"
    wf_path.write_text(builder.render(), encoding="utf-8")
    workflow = XmlWorkflowParser().parse(wf_path)

    # Without reference_capture, default Option A is pure idiomatic Pandas (no .slice)
    clean_art = ModularPackageGenerator().generate(workflow)
    assert clean_art.manifest["option_a_refinements"]["truncated_fields"] == {}
    assert ".str.slice(" not in clean_art.files["pipeline.py"]

    # With Phase 1 reference_capture showing real data hit width-3 truncation,
    # Tier 1a Option A refines ONLY .str.slice(0, 3) while keeping vectorized Pandas (exact_nodes == [])!
    p1_capture = capture_python(wf_path, output_directory=tmp_path / "p1_out")
    refined_art = ModularPackageGenerator().generate(
        workflow, reference_capture=p1_capture, reference_input_dir=tmp_path
    )
    assert refined_art.manifest["option_a_refinements"]["truncated_fields"] == {f"{sel}:code": 3, f"{sel}:region": 10}
    assert refined_art.manifest["option_a_refinements"]["exact_nodes"] == []
    assert ".str.slice(0, 3)" in refined_art.files["pipeline.py"]

    pkg_dir = tmp_path / "refined_pkg"
    p2_out = tmp_path / "p2_out"
    refined_art.write(pkg_dir)
    proc = subprocess.run(
        [sys.executable, "-I", str(pkg_dir / "cli.py"), "--input-dir", str(tmp_path), "--output-dir", str(p2_out)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert _read_csv(p2_out / "matched.csv") == [["code", "region"], ["ABC", "APAC"]]


def test_workflow_logging_and_email_events_decoupled_into_config(tmp_path: Path):
    xml = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration>
        <NumRows value="1"/><Fields><Field name="msg"/></Fields><Data><r><c>hello</c></r></Data>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput"><Position x="180" y="50"/></GuiSettings>
      <Properties><Configuration>
        <File FileFormat="0">result.csv</File>
        <FormatSpecificOptions><HeaderRow>True</HeaderRow><Delimeter>,</Delimeter><CodePage>65001</CodePage></FormatSpecificOptions>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxDbFileOutput"/>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
  </Connections>
  <Properties>
    <Events>
      <Enabled value="True"/>
      <Event>
        <EventType>RunCommand</EventType>
        <When>After</When>
        <Enabled value="True"/>
        <cmd_Program>audit_logger.exe</cmd_Program>
      </Event>
      <Event>
        <EventType>SendEmail</EventType>
        <SendMail value="True"/>
        <When>AfterNoErrors</When>
        <Enabled value="True"/>
        <email_From>bot@example.com</email_From>
        <email_To>ops@example.com</email_To>
        <email_Subject>Done</email_Subject>
        <email_Body>Attached</email_Body>
        <email_Attachments><attachment value="result.csv"/></email_Attachments>
      </Event>
    </Events>
    <RuntimeProperties/>
  </Properties>
</AlteryxDocument>
"""
    wf_path = tmp_path / "with_events.yxmd"
    wf_path.write_text(xml, encoding="utf-8")
    workflow = XmlWorkflowParser().parse(wf_path)
    artifact = ModularPackageGenerator().generate(
        workflow, delivery_profile="html-draft-v1", log_event_ids=("0",)
    )

    # Events live in config.toml and io_utils/cli lifecycle, NOT cluttering pipeline.py!
    assert "[[events.hooks]]" in artifact.files["config.toml"]
    assert "workflow_lifecycle" not in artifact.files["pipeline.py"]
    assert "workflow_lifecycle" in artifact.files["cli.py"]

    pkg_dir = tmp_path / "ev_pkg"
    out_dir = tmp_path / "ev_out"
    log_file = tmp_path / "audit.jsonl"
    artifact.write(pkg_dir)
    proc = subprocess.run(
        [
            sys.executable, "-I", str(pkg_dir / "cli.py"),
            "--output-dir", str(out_dir),
            "--workflow-log", str(log_file),
        ],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (out_dir / "result.csv").is_file()
    assert (out_dir / "event-1.eml").is_file()
    records = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["event_id"] == "0"
    assert records[0]["status"] == "success"


def test_vectorized_string_math_conditional_and_relational_operators(tmp_path: Path):
    """Exercise vectorized functions, np.where/np.select, Join, Union, Unique, RecordID, Sample, RegEx, Transpose."""
    builder = WorkflowBuilder()
    left_in = builder.add_text_input(
        ["id", "raw_name", "score", "tag"],
        [
            ["K1", "  alice smith ", "95", "vip_gold"],
            ["K2", "bob jones", "45", "std_silver"],
            ["K2", "bob jones", "45", "std_silver"],
            ["K3", "", "-10", "trial_bronze"],
        ],
    )
    right_in = builder.add_text_input(
        ["id", "tier_mult"],
        [["K1", "2"], ["K2", "1"]],
    )
    sel_l = builder.add_select(
        [("id", "True"), ("raw_name", "True"), ("score", "True"), ("tag", "True")],
        include_unknown=False,
        field_types={"score": ("Int64", 8), "raw_name": ("V_WString", 64), "tag": ("V_WString", 32)},
    )
    sel_r = builder.add_select(
        [("id", "True"), ("tier_mult", "True")],
        include_unknown=False,
        field_types={"tier_mult": ("Int64", 8)},
    )
    dedup = builder.add_unique("id")
    joined = builder.add_join("id", "id")
    calc = builder.add_formula([
        ("clean_name", "V_WString", "64", "TitleCase(Trim([raw_name]))"),
        ("padded_id", "V_WString", "16", 'PadLeft([id], 4, "0")'),
        ("upper_code", "V_WString", "16", "UpperCase(Left([tag], 3)) + '_' + LowerCase(Right([id], 1))"),
        ("mid_slice", "V_WString", "16", 'Replace(Substring([tag], 0, 4), "_", "-")'),
        ("path_col", "V_WString", "64", 'FileAddPaths([clean_name], "report.csv")'),
        ("fmt_dt", "V_WString", "16", 'DateTimeFormat("2026-03-15", "%Y/%m")'),
        ("abs_score", "Int64", "8", "Ceil([score], 1) * [tier_mult]"),
        ("band", "V_WString", "16", 'IF [score] >= 80 THEN "HIGH" ELSEIF [score] >= 40 THEN "MID" ELSE "LOW" ENDIF'),
        ("has_vip", "Bool", "1", 'Contains([tag], "vip") OR EndsWith([tag], "gold") OR StartsWith([tag], "std") AND !IsEmpty([raw_name]) AND !IsNull([score])'),
    ])
    rgx = builder.add_regex("tag", r"^([a-z]+)_", output_fields=[("tag_prefix", "V_String", 16)])
    ttc = builder.add_text_to_columns("tag", "_")
    rnk = builder.add_rank("abs_score")
    rtot = builder.add_running_total("abs_score")
    rec_id = builder.add_record_id()
    sampled = builder.add_sample("First", "5")
    sink = builder.add_csv_output("enriched.csv")

    builder.connect(left_in, sel_l)
    builder.connect(right_in, sel_r)
    builder.connect(sel_l, dedup)
    builder.connect(dedup, joined, source_anchor="Unique", target_anchor="Left")
    builder.connect(sel_r, joined, target_anchor="Right")
    builder.connect(joined, calc, source_anchor="Join")
    builder.connect(calc, rgx)
    builder.connect(rgx, ttc)
    builder.connect(ttc, rnk)
    builder.connect(rnk, rtot)
    builder.connect(rtot, rec_id)
    builder.connect(rec_id, sampled)
    builder.connect(sampled, sink)

    wf_path = tmp_path / "operators.yxmd"
    wf_path.write_text(builder.render(), encoding="utf-8")
    workflow = XmlWorkflowParser().parse(wf_path)
    p1 = capture_python(wf_path, output_directory=tmp_path / "p1")

    artifact = ModularPackageGenerator().generate(
        workflow, reference_capture=p1, reference_input_dir=tmp_path
    )
    assert "np.select" in artifact.files["pipeline.py"]
    pkg_dir = tmp_path / "ops_pkg"
    out_dir = tmp_path / "ops_out"
    artifact.write(pkg_dir)

    proc = subprocess.run(
        [sys.executable, "-I", str(pkg_dir), "--output-dir", str(out_dir)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    rows = _read_csv(out_dir / "enriched.csv")
    assert rows[0][0] == "RecordID"
    assert len(rows) == 3  # header + K1, K2


def test_union_reshape_stateful_reporting_and_loop_macros(tmp_path: Path):
    """Exercise Union, GenerateRows, MultiFieldFormula, MultiRowFormula, Message, HTML Report, Excel, and Iterative/Batch Macros."""
    # 1. Union + GenerateRows + MultiFieldFormula + MultiRowFormula + Message + Excel Output
    xml = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration>
        <NumRows value="1"/><Fields><Field name="grp"/><Field name="x"/></Fields>
        <Data><r><c>A</c><c>2</c></r></Data>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput"><Position x="50" y="130"/></GuiSettings>
      <Properties><Configuration>
        <NumRows value="1"/><Fields><Field name="grp"/><Field name="x"/></Fields>
        <Data><r><c>A</c><c>4</c></r></Data>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput"/>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Union.Union"><Position x="150" y="90"/></GuiSettings>
      <Properties><Configuration><Mode>ByName</Mode></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxUnion"/>
    </Node>
    <Node ToolID="4">
      <GuiSettings Plugin="AlteryxBasePluginsGui.GenerateRows.GenerateRows"><Position x="250" y="90"/></GuiSettings>
      <Properties><Configuration>
        <UpdateField value="False"/>
        <CreateField_Name>step_n</CreateField_Name>
        <CreateField_Type>Int32</CreateField_Type>
        <CreateField_Size>4</CreateField_Size>
        <Expression_Init>1</Expression_Init>
        <Expression_Cond>[step_n] &lt;= 2</Expression_Cond>
        <Expression_Loop>[step_n] + 1</Expression_Loop>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxGenerateRows"/>
    </Node>
    <Node ToolID="5">
      <GuiSettings Plugin="AlteryxBasePluginsGui.MultiRowFormula.MultiRowFormula"><Position x="350" y="90"/></GuiSettings>
      <Properties><Configuration>
        <UpdateField value="False"/>
        <CreateField_Name>prev_step</CreateField_Name>
        <CreateField_Type>Int32</CreateField_Type>
        <CreateField_Size>4</CreateField_Size>
        <NumRows value="1"/>
        <Expression>[Row-1:step_n] + [step_n]</Expression>
        <GroupByFields><Field field="grp"/></GroupByFields>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMultiRowFormula"/>
    </Node>
    <Node ToolID="6">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Message.Message"><Position x="450" y="90"/></GuiSettings>
      <Properties><Configuration>
        <When>First</When><Type>Message</Type><MessageExpression>"Processed group " + [grp]</MessageExpression>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMessage"/>
    </Node>
    <Node ToolID="7">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput"><Position x="550" y="90"/></GuiSettings>
      <Properties><Configuration>
        <File FileFormat="25">out.xlsx|||Sheet1</File>
        <FormatSpecificOptions><OutputOption>OverwriteFile</OutputOption></FormatSpecificOptions>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxDbFileOutput"/>
    </Node>
  </Nodes>
  <Connections>
    <Connection name="#1"><Origin ToolID="1" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
    <Connection name="#2"><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
    <Connection><Origin ToolID="3" Connection="Output"/><Destination ToolID="4" Connection="Input"/></Connection>
    <Connection><Origin ToolID="4" Connection="Output"/><Destination ToolID="5" Connection="Input"/></Connection>
    <Connection><Origin ToolID="5" Connection="Output"/><Destination ToolID="6" Connection="Input"/></Connection>
    <Connection><Origin ToolID="6" Connection="Output"/><Destination ToolID="7" Connection="Input"/></Connection>
  </Connections>
  <Properties><RuntimeProperties/></Properties>
</AlteryxDocument>
"""
    wf_path = tmp_path / "stateful.yxmd"
    wf_path.write_text(xml, encoding="utf-8")
    workflow = XmlWorkflowParser().parse(wf_path)
    artifact = ModularPackageGenerator().generate(workflow)

    pkg_dir = tmp_path / "stateful_pkg"
    out_dir = tmp_path / "stateful_out"
    artifact.write(pkg_dir)
    proc = subprocess.run(
        [sys.executable, "-I", str(pkg_dir), "--output-dir", str(out_dir)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    df_xlsx = pd.read_excel(out_dir / "out.xlsx")
    assert len(df_xlsx) == 4
    assert list(df_xlsx["prev_step"]) == [1, 3, 3, 3]

    # 2. Iterative Macro standalone execution
    iter_macro = tmp_path / "countdown.yxmc"
    iter_macro.write_text(
        """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration><Name>IterIn</Name></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"><Position x="150" y="50"/></GuiSettings>
      <Properties><Configuration><FormulaFields>
        <FormulaField expression="[n] - 1" field="n" size="8" type="Int64"/>
      </FormulaFields></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxFormula"/>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter.Filter"><Position x="250" y="50"/></GuiSettings>
      <Properties><Configuration><Mode>Custom</Mode><Expression>[n] &gt; 0</Expression></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxFilter"/>
    </Node>
    <Node ToolID="4">
      <GuiSettings Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput"><Position x="350" y="30"/></GuiSettings>
      <Properties><Configuration><Name>LoopOut</Name></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroOutput"/>
    </Node>
    <Node ToolID="5">
      <GuiSettings Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput"><Position x="350" y="100"/></GuiSettings>
      <Properties><Configuration><Name>DoneOut</Name></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroOutput"/>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
    <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
    <Connection><Origin ToolID="3" Connection="True"/><Destination ToolID="4" Connection="Input"/></Connection>
    <Connection><Origin ToolID="3" Connection="False"/><Destination ToolID="5" Connection="Input"/></Connection>
  </Connections>
  <Properties><RuntimeProperties>
    <IterativeMacro>
      <Input>IterIn</Input><Output>LoopOut</Output><IterationLimit value="15"/><LimitBehavior>Error</LimitBehavior>
    </IterativeMacro>
  </RuntimeProperties></Properties>
</AlteryxDocument>
""",
        encoding="utf-8",
    )
    iter_caller = tmp_path / "iter_run.yxmd"
    iter_caller.write_text(
        f"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration>
        <NumRows value="1"/><Fields><Field name="n"/></Fields><Data><r><c>3</c></r></Data>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings><Position x="150" y="50"/></GuiSettings>
      <Properties><Configuration/></Properties>
      <EngineSettings Macro="{iter_macro.name}"/>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput"><Position x="250" y="50"/></GuiSettings>
      <Properties><Configuration>
        <File FileFormat="0">done.csv</File>
        <FormatSpecificOptions><HeaderRow>True</HeaderRow><Delimeter>,</Delimeter><CodePage>65001</CodePage></FormatSpecificOptions>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxDbFileOutput"/>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="IterIn"/></Connection>
    <Connection><Origin ToolID="2" Connection="DoneOut"/><Destination ToolID="3" Connection="Input"/></Connection>
  </Connections>
  <Properties><RuntimeProperties/></Properties>
</AlteryxDocument>
""",
        encoding="utf-8",
    )
    iter_art = ModularPackageGenerator().generate(XmlWorkflowParser().parse(iter_caller))
    iter_pkg = tmp_path / "iter_pkg"
    iter_out = tmp_path / "iter_out"
    iter_art.write(iter_pkg)
    proc_i = subprocess.run(
        [sys.executable, "-I", str(iter_pkg), "--output-dir", str(iter_out)],
        capture_output=True, text=True, check=False,
    )
    assert proc_i.returncode == 0, proc_i.stderr
    assert _read_csv(iter_out / "done.csv") == [["n"], ["0"]]


def test_transaction_reporting_html_and_email_draft_package(tmp_path: Path, monkeypatch):
    """Compile the full transaction reporting + HTML + Email draft benchmark into a modular package."""
    import shutil

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "examples/python_pipeline_comparison"))
    from examples.python_pipeline_comparison.compare import EXAMPLE, PROFILE, build_workflow, outputs

    wf_path = tmp_path / "transactions.yxmd"
    build_workflow(wf_path)
    shutil.copyfile(EXAMPLE / "transactions.csv", tmp_path / "transactions.csv")

    workflow = XmlWorkflowParser().parse(wf_path)
    p1 = capture_python(wf_path, output_directory=tmp_path / "p1")
    artifact = ModularPackageGenerator().generate(
        workflow, delivery_profile=PROFILE, reference_capture=p1, reference_input_dir=tmp_path
    )

    pkg_dir = tmp_path / "tx_pkg"
    out_dir = tmp_path / "tx_out"
    artifact.write(pkg_dir)
    proc = subprocess.run(
        [sys.executable, "-I", str(pkg_dir), "--input-dir", str(tmp_path), "--output-dir", str(out_dir)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    observed = outputs(out_dir)
    assert observed["headers"]["Subject"] == "Posted transaction summary"
    assert len(observed["csv"]) > 1
    assert observed["html"] == observed["email_table"]


def test_crosstab_transpose_datetime_and_vectorized_lowering_edges(tmp_path: Path):
    """Exercise CrossTab, Transpose, DateTime, Tile, and vectorized_lowering scalar/casefold AST edges."""
    from alteryx2python.expressions.ast import (
        BinaryExpression,
        FieldReference,
        FunctionExpression,
        LiteralExpression,
        UnaryExpression,
    )
    from alteryx2python.generator.vectorized_lowering import try_lower_vectorized

    builder = WorkflowBuilder()
    src = builder.add_text_input(
        ["grp", "metric", "val", "dt_str"],
        [
            ["G1", "rev", "10", "2026-01-15"],
            ["G1", "cost", "4", "2026-01-15"],
            ["G2", "rev", "20", "2026-02-10"],
            ["G2", "cost", "8", "2026-02-10"],
        ],
    )
    sel = builder.add_select(
        [("grp", "True"), ("metric", "True"), ("val", "True"), ("dt_str", "True")],
        include_unknown=False,
        field_types={"val": ("Double", 8), "dt_str": ("V_WString", 16)},
    )
    dt = builder.add_datetime("dt_str", "dt_parsed", "yyyy-MM-dd")
    tiled = builder.add_tile("EqualRecords", 2, "val")
    ct = builder.add_crosstab("grp", "metric", "val", method="Sum")
    tp = builder.add_transpose(["grp"], ["rev", "cost"])
    sink = builder.add_csv_output("reshaped.csv")

    builder.connect(src, sel)
    builder.connect(sel, dt)
    builder.connect(dt, tiled)
    builder.connect(tiled, ct)
    builder.connect(ct, tp)
    builder.connect(tp, sink)

    wf_path = tmp_path / "reshape.yxmd"
    wf_path.write_text(builder.render(), encoding="utf-8")
    workflow = XmlWorkflowParser().parse(wf_path)
    artifact = ModularPackageGenerator().generate(workflow)
    pkg_dir = tmp_path / "reshape_pkg"
    out_dir = tmp_path / "reshape_out"
    artifact.write(pkg_dir)

    proc = subprocess.run(
        [sys.executable, "-I", str(pkg_dir), "--output-dir", str(out_dir)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    rows = _read_csv(out_dir / "reshaped.csv")
    assert len(rows) == 5  # header + 2 groups * 2 metrics

    # Direct AST edge coverage on try_lower_vectorized
    assert try_lower_vectorized(FunctionExpression("Null", []), "df").code == "pd.NA"
    assert "strftime" in try_lower_vectorized(
        FunctionExpression("DateTimeToday", []), "df", param_names={"__as_of__": "as_of"}
    ).code
    assert ".str.len()" in try_lower_vectorized(
        FunctionExpression("Length", [FieldReference("name")]), "df"
    ).code
    assert "len(" in try_lower_vectorized(
        FunctionExpression("Length", [LiteralExpression("abc")]), "df"
    ).code
    cf_series = try_lower_vectorized(
        BinaryExpression(FieldReference("code"), "=", LiteralExpression("ABC")),
        "df",
        known_column_kinds={"code": "string"},
        casefold_comparisons=True,
    )
    assert "casefold" in cf_series.code
    cf_two_cols = try_lower_vectorized(
        BinaryExpression(FieldReference("a"), "!=", FieldReference("b")),
        "df",
        known_column_kinds={"a": "string", "b": "string"},
        casefold_comparisons=True,
    )
    assert "casefold" in cf_two_cols.code
    special_q = try_lower_vectorized(
        BinaryExpression(
            FieldReference("Question.region"),
            "=",
            FieldReference("User.default_region"),
        ),
        "df",
        param_names={"region": "region"},
        param_meta={"region": {"kind": "DropDown"}},
        static_constants={"User.default_region": "APAC"},
        casefold_comparisons=True,
    )
    assert "casefold" in special_q.code
    neg_expr = try_lower_vectorized(UnaryExpression("-", FieldReference("val")), "df")
    assert neg_expr.code == "(-df['val'])"
    null_cmp = try_lower_vectorized(BinaryExpression(FieldReference("val"), "!=", LiteralExpression(None)), "df")
    assert null_cmp.code == "df['val'].notna()"
    assert ".lstrip()" in try_lower_vectorized(FunctionExpression("TrimLeft", [FieldReference("val")]), "df").code
    assert ".rstrip()" in try_lower_vectorized(FunctionExpression("TrimRight", [FieldReference("val")]), "df").code
    assert ".abs()" in try_lower_vectorized(FunctionExpression("Abs", [FieldReference("val")]), "df").code
    assert "pd.to_numeric" in try_lower_vectorized(
        FunctionExpression("ToNumber", [FunctionExpression("ToString", [FieldReference("val")])]), "df"
    ).code


def test_step_auditing_logs_text_jsonl_skip_redaction_and_failures(tmp_path: Path):
    """Verify template-driven step auditing across text stderr, JSONL files, secret redaction, OFF mode, and error capture."""
    from examples.python_pipeline_comparison.compare_app import TRADES, build_app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    app_path = data_dir / "transaction-app.yxwz"
    build_app(app_path)
    (data_dir / "trades.csv").write_text(TRADES, encoding="utf-8")
    (data_dir / "reports-a").mkdir()

    workflow = XmlWorkflowParser().parse(app_path)
    artifact = ModularPackageGenerator().generate(workflow)
    assert "audit_utils.py" in artifact.files
    assert "[logging]" in artifact.files["config.toml"]
    assert "audit.run_step(" in artifact.files["pipeline.py"]

    pkg_dir = tmp_path / "audited_pkg"
    artifact.write(pkg_dir)

    # 1. Default text mode logs every step (INPUT -> STEP -> STEP -> OUTPUT -> DONE) to stderr and writes JSONL to --audit-log
    out_dir = tmp_path / "out_text"
    audit_jsonl = tmp_path / "audit_trail.jsonl"
    override_cfg = tmp_path / "cfg.json"
    override_cfg.write_text(
        json.dumps({
            "parameters": {
                "report_folder": str(data_dir / "reports-a"),
                "api_token": "super-secret-token-123",
            }
        }),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-I",
            str(pkg_dir),
            "--config",
            str(override_cfg),
            "--input-dir",
            str(data_dir),
            "--output-dir",
            str(out_dir),
            "--audit-log",
            str(audit_jsonl),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert [p.name for p in out_dir.iterdir()] == ["report.csv"]

    assert "START pipeline" in proc.stderr
    assert "[Step 1] INPUT trades (DbFileInput #1) | 3 rows x 4 cols" in proc.stderr
    assert "[Step 2] STEP select_trade_id_and_region (Select #2)" in proc.stderr
    assert "[Step 3] STEP compute_include_flag_and_report_date (Formula->Filter->Select #5,6,7)" in proc.stderr
    assert "3x4 -> 1x6 (rows -2" in proc.stderr
    assert "[Step 4] OUTPUT report (DbFileOutput #8) | 1 rows x 6 cols" in proc.stderr
    assert "-> report.csv" in proc.stderr
    assert "DONE pipeline | steps=4 | outputs=1" in proc.stderr
    assert "super-secret-token-123" not in proc.stderr
    assert "***REDACTED***" in proc.stderr
    assert "T001" not in proc.stderr

    records = [json.loads(line) for line in audit_jsonl.read_text(encoding="utf-8").splitlines()]
    assert [r["kind"] for r in records] == ["pipeline_start", "input", "transform", "transform", "output", "pipeline_end"]
    assert records[0]["parameters"]["api_token"] == "***REDACTED***"
    assert records[3]["row_delta"] == -2
    assert "display_amount" in records[3]["columns_added"]
    assert "status" in records[3]["columns_removed"]

    # 2. --log-level OFF silences stderr completely while preserving normal execution
    out_off = tmp_path / "out_off"
    proc_off = subprocess.run(
        [
            sys.executable,
            "-I",
            str(pkg_dir),
            "--config",
            str(override_cfg),
            "--input-dir",
            str(data_dir),
            "--output-dir",
            str(out_off),
            "--log-level",
            "OFF",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_off.returncode == 0
    assert proc_off.stderr == ""
    assert _read_csv(out_off / "report.csv") == _read_csv(out_dir / "report.csv")

    # 3. Runtime failure logs FAIL audit record with step & error details before propagating exception
    bad_dir = tmp_path / "empty_in_dir"
    bad_dir.mkdir()
    bad_audit = tmp_path / "failed_audit.jsonl"
    proc_fail = subprocess.run(
        [
            sys.executable,
            "-I",
            str(pkg_dir),
            "--input-dir",
            str(bad_dir),
            "--output-dir",
            str(tmp_path / "out_fail"),
            "--log-format",
            "jsonl",
            "--audit-log",
            str(bad_audit),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_fail.returncode != 0
    fail_records = [json.loads(line) for line in bad_audit.read_text(encoding="utf-8").splitlines()]
    assert fail_records[-1]["kind"] == "pipeline_end"
    assert fail_records[-1]["status"] == "failed"
    assert fail_records[-1]["error_type"] == "FileNotFoundError"




