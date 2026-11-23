"""Tests for Phase 2 IR graph optimization and redundancy elimination."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd

from alteryx2python.generator.ir_optimizer import optimize_workflow_ir
from alteryx2python.generator.parameters import ParameterExpression, prepare_parameters
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.workflow_generator import WorkflowBuilder


def _parse(builder: WorkflowBuilder, tmp_path: Path, name: str = "workflow.yxmd"):
    path = tmp_path / name
    path.write_text(builder.render(), encoding="utf-8")
    return XmlWorkflowParser().parse(path)


def test_select_chain_fusion_and_dead_column_pruning_match_phase1(tmp_path: Path):
    builder = WorkflowBuilder()
    src = builder.add_text_input(
        ["raw_id", "raw_amt", "unused_col", "temp_note"],
        [["A1", "10", "junk1", "note1"], ["A2", "25", "junk2", "note2"]],
    )
    # Select 1: rename raw_id -> id, raw_amt -> amount, keep unused_col & temp_note
    s1 = builder._node(
        "Select",
        """
        <OrderChanged value="False"/>
        <SelectFields>
          <SelectField field="raw_id" rename="id" selected="True"/>
          <SelectField field="raw_amt" rename="amount" selected="True"/>
          <SelectField field="unused_col" selected="True"/>
          <SelectField field="temp_note" selected="True"/>
          <SelectField field="*Unknown" selected="False"/>
        </SelectFields>
        """,
        (160, 186),
    )
    # Identity Select (passthrough *Unknown)
    s_id = builder.add_select([], include_unknown=True)
    # Select 2: rename id -> trade_id, cast amount -> Int64, drop temp_note
    s2 = builder._node(
        "Select",
        """
        <OrderChanged value="False"/>
        <SelectFields>
          <SelectField field="id" rename="trade_id" selected="True"/>
          <SelectField field="amount" selected="True" type="Int64" size="8"/>
          <SelectField field="unused_col" selected="True"/>
          <SelectField field="temp_note" selected="False"/>
          <SelectField field="*Unknown" selected="False"/>
        </SelectFields>
        """,
        (320, 186),
    )
    # Formula uses amount, never reads unused_col
    f1 = builder.add_formula([("doubled", "Int64", "8", "[amount] * 2")])
    # Terminal Select drops unused_col and amount, keeping trade_id & doubled
    s3 = builder.add_select(
        [("trade_id", "True"), ("doubled", "True")],
        include_unknown=False,
    )
    sink = builder.add_csv_output("out.csv")
    browse = builder._node("BrowseV2", "", (600, 100))

    builder.connect(src, s1)
    builder.connect(s1, s_id)
    builder.connect(s_id, s2)
    builder.connect(s2, f1)
    builder.connect(f1, s3)
    builder.connect(f1, browse)
    builder.connect(s3, sink)

    workflow = _parse(builder, tmp_path)
    opt = optimize_workflow_ir(workflow)

    # Identity select, chained s2, and BrowseV2 must be eliminated/fused
    assert opt.provenance[str(s_id)]["reason"] == "identity_select"
    assert opt.provenance[str(s2)]["status"] == "fused"
    assert opt.provenance[str(browse)]["reason"] == "ui_noop:BrowseV2"

    # unused_col should be pruned early at s1
    fused_select = next(n for n in opt.workflow.nodes if n.node_id == str(s1))
    kept_cols = [
        f["rename"]
        for f in fused_select.config["normalized"]["select_fields"]
        if f["selected"] and f["source"] != "*Unknown"
    ]
    assert "unused_col" not in kept_cols
    assert kept_cols == ["trade_id", "amount"]

    # Execute both unoptimized and optimized workflows and compare output CSVs
    out_orig = tmp_path / "orig_out"
    out_opt = tmp_path / "opt_out"
    run_workflow_graph(workflow, WorkflowContext(runtime_config={"output_dir": out_orig}))
    run_workflow_graph(opt.workflow, WorkflowContext(runtime_config={"output_dir": out_opt}))
    # Redirected or source-relative sink output matches identically
    orig_res = run_workflow_graph(workflow, WorkflowContext())
    opt_res = run_workflow_graph(opt.workflow, WorkflowContext())
    pd.testing.assert_frame_equal(
        orig_res.node_results[str(s3)].outputs["Output"],
        opt_res.node_results[str(s3)].outputs["Output"],
    )


def test_select_chain_preserves_lossy_narrow_truncation(tmp_path: Path):
    builder = WorkflowBuilder()
    src = builder.add_text_input(["code"], [["ABCDEF"]])
    s1 = builder.add_select([("code", "True")], include_unknown=False, field_types={"code": ("V_WString", 3)})
    s2 = builder.add_select([("code", "True")], include_unknown=False, field_types={"code": ("V_WString", 10)})
    builder.connect(src, s1)
    builder.connect(s1, s2)
    workflow = _parse(builder, tmp_path)
    opt = optimize_workflow_ir(workflow)
    # Both Selects must remain separate so width-3 truncation happens before width-10
    select_ids = [n.node_id for n in opt.workflow.nodes if n.tool_type == "Select"]
    assert select_ids == [str(s1), str(s2)]


def test_formula_fusion_preserves_sequential_filter_boundaries(tmp_path: Path):
    builder = WorkflowBuilder()
    src = builder.add_text_input(
        ["region", "status", "qty", "price"],
        [
            ["APAC", "cancelled", "3", "10"],
            ["APAC", "posted", "4", "20"],
            ["EMEA", "posted", "5", "20"],
        ],
    )
    s0 = builder.add_select(
        [("region", "True"), ("status", "True"), ("qty", "True"), ("price", "True")],
        include_unknown=False,
        field_types={"qty": ("Int64", 8), "price": ("Int64", 8)},
    )
    f1 = builder.add_formula([("gross", "Int64", "8", "[qty] * [price]")])
    f2 = builder.add_formula([("net", "Int64", "8", "[gross] - 5")])
    flt1 = builder.add_filter('[status] = "cancelled"')
    # Connect False branch of flt1 -> flt2!
    flt2 = builder.add_filter('[region] = "APAC" AND [net] > 50')
    sink = builder.add_csv_output("filtered.csv")

    builder.connect(src, s0)
    builder.connect(s0, f1)
    builder.connect(f1, f2)
    builder.connect(f2, flt1)
    builder.connect(flt1, flt2, source_anchor="False")
    builder.connect(flt2, sink, source_anchor="True")

    workflow = _parse(builder, tmp_path)
    opt = optimize_workflow_ir(workflow)

    assert len([n for n in opt.workflow.nodes if n.tool_type == "Formula"]) == 1
    assert len([n for n in opt.workflow.nodes if n.tool_type == "Filter"]) == 2
    assert opt.provenance[str(f2)]["reason"] == "fused_formula_chain"
    assert opt.provenance[str(flt2)]["status"] == "retained"

    orig_res = run_workflow_graph(workflow, WorkflowContext())
    opt_res = run_workflow_graph(opt.workflow, WorkflowContext())
    expected = orig_res.node_results[str(flt2)].outputs["True"].reset_index(drop=True)
    actual = opt_res.node_results[str(flt2)].outputs["True"].reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected)


def test_filter_with_both_branches_consumed_is_not_fused(tmp_path: Path):
    builder = WorkflowBuilder()
    src = builder.add_text_input(["x"], [["1"], ["2"], ["3"]])
    s0 = builder.add_select([("x", "True")], include_unknown=False, field_types={"x": ("Int64", 8)})
    flt1 = builder.add_filter("[x] > 1")
    flt2 = builder.add_filter("[x] > 2")
    sink_t = builder.add_csv_output("t.csv")
    sink_f = builder.add_csv_output("f.csv")
    builder.connect(src, s0)
    builder.connect(s0, flt1)
    builder.connect(flt1, flt2, source_anchor="True")
    builder.connect(flt1, sink_f, source_anchor="False")
    builder.connect(flt2, sink_t, source_anchor="True")

    workflow = _parse(builder, tmp_path)
    opt = optimize_workflow_ir(workflow)
    assert len([n for n in opt.workflow.nodes if n.tool_type == "Filter"]) == 2


def test_seven_question_app_folds_parameter_table_in_dynamic_mode(tmp_path: Path):
    from examples.python_pipeline_comparison.compare_app import TRADES, build_app

    app_path = tmp_path / "transaction-app.yxwz"
    build_app(app_path)
    (tmp_path / "trades.csv").write_text(TRADES, encoding="utf-8")
    (tmp_path / "reports-a").mkdir()

    workflow = XmlWorkflowParser().parse(app_path)
    prepared, param_exprs, param_specs = prepare_parameters(workflow, None)
    opt = optimize_workflow_ir(
        prepared,
        parameters=param_specs,
        parameter_bindings=prepared.metadata.get("parameter_bindings", []),
        parameter_expressions=param_exprs,
    )

    tool_types = [n.tool_type for n in opt.workflow.nodes]
    # Both the 1-row TextInput and AppendFields must be completely eliminated!
    assert "TextInput" not in tool_types
    assert "AppendFields" not in tool_types
    # Parameter expressions must reference ParameterExpression directly
    formula_node = next(n for n in opt.workflow.nodes if n.tool_type == "Formula")
    expr_asts = [
        opt.parameter_expressions.get((formula_node.node_id, ("formula_fields", idx, "expression")))
        for idx in range(5)
    ]
    assert all(ast_node is not None for ast_node in expr_asts)
    used_params = {
        item.name
        for ast_node in expr_asts
        for item in _walk_expr(ast_node)
        if isinstance(item, ParameterExpression)
    }
    assert {"include_archived", "report_date", "suffix", "detail", "summary"} <= used_params


def test_static_single_row_parameter_table_folds_into_config_parameters(tmp_path: Path):
    builder = WorkflowBuilder()
    data = builder.add_text_input(["item", "price"], [["Book", "20"], ["Pen", "5"]])
    typed = builder.add_select(
        [("item", "True"), ("price", "True")],
        include_unknown=False,
        field_types={"price": ("Int64", 8)},
    )
    params = builder.add_text_input(["tax_multiplier", "currency_tag"], [["2", "USD"]])
    append = builder._node(
        "AppendFields",
        """
        <CartesianMode>Error</CartesianMode>
        <SelectConfiguration><Configuration outputConnection="Output">
          <OrderChanged value="False"/><CommaDecimal value="False"/>
          <SelectFields><SelectField field="*Unknown" selected="True"/></SelectFields>
        </Configuration></SelectConfiguration>
        """,
        (220, 200),
    )
    calc = builder.add_formula([
        ("taxed", "Int64", "8", "[price] * [tax_multiplier]"),
        ("tagged", "V_WString", "32", '[item] + "-" + [currency_tag]'),
    ])
    out_sel = builder.add_select([("tagged", "True"), ("taxed", "True")], include_unknown=False)
    sink = builder.add_csv_output("items.csv")

    builder.connect(data, typed)
    builder.connect(typed, append, target_anchor="Targets")
    builder.connect(params, append, target_anchor="Source")
    builder.connect(append, calc)
    builder.connect(calc, out_sel)
    builder.connect(out_sel, sink)

    workflow = _parse(builder, tmp_path)
    opt = optimize_workflow_ir(workflow)

    assert "AppendFields" not in [n.tool_type for n in opt.workflow.nodes]
    assert str(params) not in {n.node_id for n in opt.workflow.nodes}
    folded_names = {p["name"]: p["default"] for p in opt.parameters}
    assert folded_names == {"tax_multiplier": 2, "currency_tag": "USD"}


def _write_standard_macro(path: Path) -> None:
    macro_xml = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration><Name>Input</Name></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect"><Position x="150" y="50"/></GuiSettings>
      <Properties><Configuration>
        <OrderChanged value="False"/>
        <SelectFields>
          <SelectField field="val" selected="True" type="Int64" size="8"/>
          <SelectField field="*Unknown" selected="True"/>
        </SelectFields>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxSelect"/>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"><Position x="250" y="50"/></GuiSettings>
      <Properties><Configuration><FormulaFields>
        <FormulaField expression="[val] + 10" field="val" size="8" type="Int64"/>
      </FormulaFields></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxFormula"/>
    </Node>
    <Node ToolID="4">
      <GuiSettings Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput"><Position x="350" y="50"/></GuiSettings>
      <Properties><Configuration><Name>Output</Name></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroOutput"/>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
    <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
    <Connection><Origin ToolID="3" Connection="Output"/><Destination ToolID="4" Connection="Input"/></Connection>
  </Connections>
  <Properties><RuntimeProperties/></Properties>
</AlteryxDocument>
"""
    path.write_text(macro_xml, encoding="utf-8")


def test_single_call_macro_inlines_and_fuses_with_outer_select_and_formula(tmp_path: Path):
    macro_path = tmp_path / "add_ten.yxmc"
    _write_standard_macro(macro_path)

    wf_xml = f"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="10">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration>
        <NumRows value="1"/><Fields><Field name="raw_val"/></Fields><Data><r><c>5</c></r></Data>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput"/>
    </Node>
    <Node ToolID="11">
      <GuiSettings Plugin="AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect"><Position x="140" y="50"/></GuiSettings>
      <Properties><Configuration><OrderChanged value="False"/><SelectFields>
        <SelectField field="raw_val" rename="val" selected="True"/>
      </SelectFields></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxSelect"/>
    </Node>
    <Node ToolID="12">
      <GuiSettings Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer"><Position x="200" y="20"/></GuiSettings>
      <Properties><Configuration><Caption>Wrap</Caption><Disabled value="False"/></Configuration></Properties>
      <ChildNodes>
        <Node ToolID="13">
          <GuiSettings><Position x="240" y="50"/></GuiSettings>
          <Properties><Configuration/></Properties>
          <EngineSettings Macro="{macro_path.name}"/>
        </Node>
      </ChildNodes>
    </Node>
    <Node ToolID="14">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"><Position x="360" y="50"/></GuiSettings>
      <Properties><Configuration><FormulaFields>
        <FormulaField expression="[val] * 2" field="final_val" size="8" type="Int64"/>
      </FormulaFields></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxFormula"/>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="10" Connection="Output"/><Destination ToolID="11" Connection="Input"/></Connection>
    <Connection><Origin ToolID="11" Connection="Output"/><Destination ToolID="13" Connection="Input"/></Connection>
    <Connection><Origin ToolID="13" Connection="Output"/><Destination ToolID="14" Connection="Input"/></Connection>
  </Connections>
  <Properties><RuntimeProperties/></Properties>
</AlteryxDocument>
"""
    wf_path = tmp_path / "caller.yxmd"
    wf_path.write_text(wf_xml, encoding="utf-8")
    workflow = XmlWorkflowParser().parse(wf_path)
    opt = optimize_workflow_ir(workflow)

    # Outer Select 11 + Macro inner Select 2 fuse into ONE Select;
    # Macro inner Formula 3 + Outer Formula 14 fuse into ONE Formula!
    types = [n.tool_type for n in opt.workflow.nodes]
    assert types == ["TextInput", "Select", "Formula"]

    orig_res = run_workflow_graph(workflow, WorkflowContext())
    opt_res = run_workflow_graph(opt.workflow, WorkflowContext())
    expected = orig_res.node_results["14"].outputs["Output"]
    actual = opt_res.node_results["13__3"].outputs["Output"]
    pd.testing.assert_frame_equal(actual, expected)


def test_multi_call_macro_deduplicates_into_single_reusable_subgraph(tmp_path: Path):
    macro_path = tmp_path / "add_ten.yxmc"
    _write_standard_macro(macro_path)

    wf_xml = f"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration>
        <NumRows value="1"/><Fields><Field name="val"/></Fields><Data><r><c>5</c></r></Data>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings><Position x="150" y="50"/></GuiSettings>
      <Properties><Configuration/></Properties>
      <EngineSettings Macro="{macro_path.name}"/>
    </Node>
    <Node ToolID="3">
      <GuiSettings><Position x="250" y="50"/></GuiSettings>
      <Properties><Configuration/></Properties>
      <EngineSettings Macro="{macro_path.name}"/>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
    <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
  </Connections>
  <Properties><RuntimeProperties/></Properties>
</AlteryxDocument>
"""
    wf_path = tmp_path / "two_calls.yxmd"
    wf_path.write_text(wf_xml, encoding="utf-8")
    workflow = XmlWorkflowParser().parse(wf_path)
    opt = optimize_workflow_ir(workflow)

    assert len(opt.reusable_macros) == 1
    calls = [n for n in opt.workflow.nodes if n.tool_type == "MacroSubgraphCall"]
    assert len(calls) == 2
    assert calls[0].metadata["reusable_macro_key"] == calls[1].metadata["reusable_macro_key"]


def test_iterative_macro_extracts_loop_macro_spec(tmp_path: Path):
    iter_macro = tmp_path / "halve_until_small.yxmc"
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
      <Input>IterIn</Input>
      <Output>LoopOut</Output>
      <IterationLimit value="25"/>
      <LimitBehavior>Error</LimitBehavior>
    </IterativeMacro>
  </RuntimeProperties></Properties>
</AlteryxDocument>
""",
        encoding="utf-8",
    )

    caller = tmp_path / "iter_caller.yxmd"
    caller.write_text(
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
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="IterIn"/></Connection>
  </Connections>
  <Properties><RuntimeProperties/></Properties>
</AlteryxDocument>
""",
        encoding="utf-8",
    )
    workflow = XmlWorkflowParser().parse(caller)
    opt = optimize_workflow_ir(workflow)
    assert len(opt.loop_macros) == 1
    spec = next(iter(opt.loop_macros.values()))
    assert spec.kind == "iterative"
    assert spec.iteration_input == "IterIn"
    assert spec.iteration_output == "LoopOut"
    assert spec.iteration_limit == 25
    assert spec.output_anchors == ["DoneOut"]


def test_batch_macro_and_disabled_container_guard_boundaries(tmp_path: Path):
    batch_macro = tmp_path / "scale_batch.yxmc"
    batch_macro.write_text(
        """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration><Name>DataIn</Name></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"><Position x="150" y="50"/></GuiSettings>
      <Properties><Configuration><FormulaFields>
        <FormulaField expression="[x] * 2" field="scaled" size="8" type="Int64"/>
      </FormulaFields></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxFormula"/>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput"><Position x="250" y="50"/></GuiSettings>
      <Properties><Configuration><Name>Out</Name></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroOutput"/>
    </Node>
    <Node ToolID="10">
      <GuiSettings Plugin="AlteryxGuiToolkit.Questions.ControlParam.ControlParam"><Position x="150" y="10"/></GuiSettings>
      <Properties><Configuration/></Properties>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
    <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
  </Connections>
  <Properties><RuntimeProperties>
    <BatchMacro><OutputMode>AllSame</OutputMode></BatchMacro>
    <Questions><Question>
      <Type>Tab</Type><Name>Questions</Name>
      <Questions><Question><Type>ControlParam</Type><Description>Factor</Description><Name>factor</Name><ToolId value="10"/></Question></Questions>
    </Question></Questions>
  </RuntimeProperties></Properties>
</AlteryxDocument>
""",
        encoding="utf-8",
    )

    caller = tmp_path / "batch_caller.yxmd"
    caller.write_text(
        f"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2025.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput"><Position x="50" y="50"/></GuiSettings>
      <Properties><Configuration>
        <NumRows value="1"/><Fields><Field name="x"/></Fields><Data><r><c>4</c></r></Data>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput"/>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput"><Position x="50" y="150"/></GuiSettings>
      <Properties><Configuration>
        <NumRows value="2"/><Fields><Field name="factor"/></Fields><Data><r><c>2</c></r><r><c>3</c></r></Data>
      </Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput"/>
    </Node>
    <Node ToolID="3">
      <GuiSettings><Position x="180" y="100"/></GuiSettings>
      <Properties><Configuration><Value name="ControlParams">factor=factor</Value></Configuration></Properties>
      <EngineSettings Macro="{batch_macro.name}"/>
    </Node>
    <Node ToolID="4">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"><Position x="280" y="100"/></GuiSettings>
      <Properties><Configuration><FormulaFields>
        <FormulaField expression="[scaled] + 1" field="a" size="8" type="Int64"/>
      </FormulaFields></Configuration></Properties>
      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxFormula"/>
    </Node>
    <Node ToolID="5">
      <GuiSettings Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer"><Position x="360" y="60"/></GuiSettings>
      <Properties><Configuration><Caption>DisabledBox</Caption><Disabled value="True"/></Configuration></Properties>
      <ChildNodes>
        <Node ToolID="6">
          <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"><Position x="380" y="100"/></GuiSettings>
          <Properties><Configuration><FormulaFields>
            <FormulaField expression="[a] + 1" field="b" size="8" type="Int64"/>
          </FormulaFields></Configuration></Properties>
          <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxFormula"/>
        </Node>
      </ChildNodes>
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="3" Connection="DataIn"/></Connection>
    <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Control"/></Connection>
    <Connection><Origin ToolID="3" Connection="Out"/><Destination ToolID="4" Connection="Input"/></Connection>
    <Connection><Origin ToolID="4" Connection="Output"/><Destination ToolID="6" Connection="Input"/></Connection>
  </Connections>
  <Properties><RuntimeProperties/></Properties>
</AlteryxDocument>
""",
        encoding="utf-8",
    )
    workflow = XmlWorkflowParser().parse(caller)
    opt = optimize_workflow_ir(workflow)
    assert len(opt.loop_macros) == 1
    spec = next(iter(opt.loop_macros.values()))
    assert spec.kind == "batch"
    assert spec.control_param == "factor"
    # Formula 4 (enabled) and Formula 6 (inside disabled container 5) MUST NOT fuse across container guard!
    formulas = [n.node_id for n in opt.workflow.nodes if n.tool_type == "Formula"]
    assert formulas == ["4", "6"]


def test_single_row_parameter_table_surviving_column_materializes_as_formula(tmp_path: Path):
    builder = WorkflowBuilder()
    data = builder.add_text_input(["item"], [["Widget"]])
    typed = builder.add_select([("item", "True")], include_unknown=False)
    params = builder.add_text_input(["batch_date", "active", "rate"], [["2026-11-21", "True", "1.25"]])
    append = builder._node(
        "AppendFields",
        """
        <CartesianMode>Error</CartesianMode>
        <SelectConfiguration><Configuration outputConnection="Output">
          <OrderChanged value="False"/><CommaDecimal value="False"/>
          <SelectFields><SelectField field="*Unknown" selected="True"/></SelectFields>
        </Configuration></SelectConfiguration>
        """,
        (220, 200),
    )
    # Direct sink without dropping batch_date / active / rate!
    sink = builder.add_csv_output("surviving.csv")
    builder.connect(data, typed)
    builder.connect(typed, append, target_anchor="Targets")
    builder.connect(params, append, target_anchor="Source")
    builder.connect(append, sink)

    workflow = _parse(builder, tmp_path)
    opt = optimize_workflow_ir(workflow)
    assert "AppendFields" not in [n.tool_type for n in opt.workflow.nodes]
    assert "Formula" in [n.tool_type for n in opt.workflow.nodes]
    by_name = {p["name"]: (p["kind"], p["default"]) for p in opt.parameters}
    assert by_name["batch_date"] == ("Date", "2026-11-21")
    assert by_name["active"] == ("BooleanGroup", True)
    assert by_name["rate"] == ("NumericUpDown", 1.25)


def _walk_expr(node):
    from dataclasses import fields, is_dataclass

    yield node
    if is_dataclass(node):
        for f in fields(node):
            val = getattr(node, f.name)
            if is_dataclass(val):
                yield from _walk_expr(val)
            elif isinstance(val, list):
                for item in val:
                    if is_dataclass(item):
                        yield from _walk_expr(item)
