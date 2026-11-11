"""Engine component coverage: variables, python tool, actions, nested macros."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from alteryx2python.engine_variables import (
    engine_constants,
    resolve_config_tokens,
    resolve_tokens,
)
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.tools.jupytercode import jupytercode_tool


def test_engine_constant_table_names_match_dll_harvest():
    constants = engine_constants()
    expected = {
        "WorkflowDirectory", "WorkflowFileName", "TempFilePath", "ModuleDirectory",
        "IterationNumber", "OS", "Version", "Type", "ReportFont", "GuiInteraction",
    }
    assert expected <= set(constants)


def test_resolve_tokens_question_engine_and_temp():
    constants = {"TempFilePath": "C:/tmp/x", "OS": "Windows"}
    resolved = resolve_tokens(
        "%Question.Limit%|%temp%|%Engine.OS%|%Question.Missing%",
        answers={"Limit": 7},
        constants=constants,
    )
    assert resolved == "7|C:/tmp/x|Windows|%Question.Missing%"


def test_resolve_config_tokens_recurses_structures():
    config = {
        "expression": "[Qty] >= %Question.Min%",
        "nested": {"file": "%temp%/out.csv"},
        "items": ["%Question.X%", "plain"],
    }
    resolved = resolve_config_tokens(
        config, answers={"Min": 3, "X": "x"}, constants={"TempFilePath": "T"}
    )
    assert resolved["expression"] == "[Qty] >= 3"
    assert resolved["nested"]["file"] == "T/out.csv"
    assert resolved["items"][0] == "x"


def test_expression_engine_constants_via_field_reference():
    node = parse_expression("[Engine.OS] == 'Windows'")
    assert evaluate_expression(node, {}, engine_constants()) is True


def _tokens_workflow(tmp_path: Path) -> Path:
    xml = (
        '<?xml version="1.0"?><AlteryxDocument yxmdVer="2022.1"><Nodes>'
        '<Node ToolID="1"><GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput">'
        '<Position x="54" y="186" /></GuiSettings><Properties><Configuration>'
        '<NumRows value="3" /><Fields><Field name="Qty" /></Fields><Data>'
        '<r><c>1</c></r><r><c>5</c></r><r><c>9</c></r></Data></Configuration>'
        '<Annotation DisplayMode="0"><Name /><DefaultAnnotationText /><Left value="False" /></Annotation>'
        '</Properties>'
        '<EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput" />'
        '</Node>'
        '<Node ToolID="2"><GuiSettings Plugin="AlteryxBasePluginsGui.Filter.Filter">'
        '<Position x="250" y="186" /></GuiSettings><Properties><Configuration>'
        '<Mode>Custom</Mode><Simple /><Expression>[Qty] &gt;= %Question.Min%</Expression></Configuration>'
        '<Annotation DisplayMode="0"><Name /><DefaultAnnotationText /><Left value="False" /></Annotation>'
        '</Properties>'
        '<EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxFilter" />'
        '</Node></Nodes>'
        '<Connections><Connection><Origin ToolID="1" Connection="Output" />'
        '<Destination ToolID="2" Connection="Input" /></Connection></Connections>'
        '<Properties><Memory default="True" /><GlobalRecordLimit value="0" />'
        '<RuntimeProperties><Actions />'
        '<Questions><Question><Type>NumericUpDown</Type><Description>min</Description>'
        '<Name>Min</Name><ToolId value="9" /><Default>1</Default></Question>'
        '</Questions></RuntimeProperties></Properties>'
        '</AlteryxDocument>'
    )
    path = tmp_path / "tokens.yxmd"
    path.write_text(xml, encoding="utf-8")
    return path


def test_executor_resolves_question_tokens_in_configs(tmp_path):
    workflow = XmlWorkflowParser().parse(_tokens_workflow(tmp_path))
    context = WorkflowContext(runtime_config={"answers": {"Min": "5"}})
    result = run_workflow_graph(workflow, context, target_node_ids={"2"})
    frame = result.node_results["2"].outputs["True"]
    assert list(frame["Qty"]) == [5, 9]


def test_jupytercode_executes_bridge_script():
    script = (
        "from ayx import Alteryx\n"
        "df = Alteryx.read('#1')\n"
        "df = df.assign(Doubled=df['Qty'] * 2)\n"
        "Alteryx.write(df, '#1')\n"
    )
    inputs = {"1": pd.DataFrame({"Name": ["a", "b"], "Qty": [1, 2]})}
    result = jupytercode_tool(
        inputs, {"production_mode_script": script, "node_id": "7"}, WorkflowContext()
    )
    assert list(result["Output"]["Doubled"]) == [2, 4]


def test_jupytercode_extracts_notebook_json_code_cells():
    from alteryx2python.tools.jupytercode import _extract_notebook_code

    notebook = '{"cells": [{"cell_type": "code", "source": ["x = 1' + chr(92) + 'n"]}, {"cell_type": "markdown", "source": ["text"]}]}'
    assert _extract_notebook_code(notebook) == "x = 1" + chr(10)


# ---- action tool: extended update modes -------------------------------------


def _app_xml(tmp_path: Path) -> Path:
    xml = (
        '<?xml version="1.0"?><AlteryxDocument yxmdVer="2022.1"><Nodes>'
        '<Node ToolID="1"><GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput">'
        '<Position x="54" y="186" /></GuiSettings><Properties><Configuration>'
        '<NumRows value="1" /><Fields><Field name="A" /><Field name="B" /></Fields><Data>'
        '<r><c>1</c><c>2</c></r></Data></Configuration>'
        '<Annotation DisplayMode="0"><Name /><DefaultAnnotationText /><Left value="False" /></Annotation>'
        '</Properties>'
        '<EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput" />'
        '</Node>'
        '<Node ToolID="2"><GuiSettings Plugin="AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect">'
        '<Position x="250" y="186" /></GuiSettings><Properties><Configuration>'
        '<OrderChanged value="False" /><CommaDecimal value="False" />'
        '<SelectFields>'
        '<SelectField field="A" selected="True" />'
        '<SelectField field="B" selected="True" />'
        '<SelectField field="*Unknown" selected="True" />'
        '</SelectFields></Configuration>'
        '<Annotation DisplayMode="0"><Name /><DefaultAnnotationText /><Left value="False" /></Annotation>'
        '</Properties>'
        '<EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxSelect" />'
        '</Node></Nodes>'
        '<Connections><Connection><Origin ToolID="1" Connection="Output" />'
        '<Destination ToolID="2" Connection="Input" /></Connection></Connections>'
        '<Properties><Memory default="True" />'
        '<RuntimeProperties>'
        '<Actions><NoCondition><Type>NoCondition</Type><Description>(Always Run)</Description><True>'
        '<Action><Type>UpdateSelect</Type><Description /><ToolId value="2" />'
        '<Variable>pick</Variable><Destination>2/SelectFields</Destination></Action>'
        '</True></NoCondition></Actions>'
        '<Questions><Question><Type>ListBox</Type><Description>pick</Description>'
        '<Name>pick</Name><ToolId value="9" /><Default>A</Default></Question></Questions>'
        '</RuntimeProperties></Properties></AlteryxDocument>'
    )
    path = tmp_path / "app.yxwz"
    path.write_text(xml, encoding="utf-8")
    return path


def test_update_select_action_marks_only_selected_fields(tmp_path):
    from alteryx2python.runtime.app_config import configure_workflow

    configured, values = configure_workflow(_app_xml(tmp_path), {"pick": "A"})
    assert values["pick"] in ("A", ["A"])
    select_fields = configured.findall(".//Node[@ToolID='2']//SelectField")
    state = {field.get("field"): field.get("selected") for field in select_fields}
    assert state["A"] == "True"
    assert state["B"] == "False"
    assert state["*Unknown"] == "True"


def test_delete_tool_action_removes_node_and_edges(tmp_path):
    from alteryx2python.runtime.app_config import configure_workflow

    path = _app_xml(tmp_path)
    xml = path.read_text(encoding="utf-8").replace(
        "<Type>UpdateSelect</Type><Description /><ToolId value=\"2\" />"
        "<Variable>pick</Variable><Destination>2/SelectFields</Destination>",
        "<Type>DeleteTool</Type><Description /><ToolId value=\"2\" />"
        "<Variable>pick</Variable><Destination>2/Configuration</Destination>",
    )
    path.write_text(xml, encoding="utf-8")
    configured, _ = configure_workflow(path, {"pick": "True"})
    assert configured.find(".//Node[@ToolID='2']") is None
    assert len(configured.findall("./Connections/Connection")) == 0


# ---- nested macros -----------------------------------------------------------


def _macro_node(tool_id: str, plugin: str, position: str, config: str, engine: str) -> str:
    return (
        f'<Node ToolID="{tool_id}"><GuiSettings Plugin="{plugin}">'
        f'<Position x="{position}" y="186" /></GuiSettings><Properties>'
        f'<Configuration>{config}</Configuration>'
        '<Annotation DisplayMode="0"><Name /><DefaultAnnotationText /><Left value="False" /></Annotation>'
        f'</Properties>{engine}</Node>'
    )


def test_nested_macro_executes_through_macro_engine(tmp_path):
    """A macro whose body calls another shipped macro executes recursively."""
    inner = Path("D:/Alteryx/bin/RuntimeData/Macros/CountRecords.yxmc")
    if not inner.exists():
        pytest.skip("shipped macro library not installed")

    engine_input = '<EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroInput" />'
    engine_output = '<EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxMacroOutput" />'
    engine_inner = '<EngineSettings Macro="CountRecords.yxmc" />'
    outer = tmp_path / "outer.yxmc"
    outer.write_text(
        '<?xml version="1.0"?><AlteryxDocument yxmdVer="2022.1"><Nodes>'
        + _macro_node("1", "AlteryxBasePluginsGui.MacroInput.MacroInput", "54",
                      "<Name>Input</Name><AnchorName>Input</AnchorName>", engine_input)
        + _macro_node("2", "CountRecords.yxmc", "250", "", engine_inner)
        + _macro_node("3", "AlteryxBasePluginsGui.MacroOutput.MacroOutput", "450",
                      "<Name>Output</Name><AnchorName>Output</AnchorName>", engine_output)
        + '</Nodes>'
        '<Connections><Connection><Origin ToolID="1" Connection="Output" />'
        '<Destination ToolID="2" Connection="Input" /></Connection>'
        '<Connection><Origin ToolID="2" Connection="Output9" />'
        '<Destination ToolID="3" Connection="Input" /></Connection></Connections>'
        '<Properties><Memory default="True" /><GlobalRecordLimit value="0" />'
        '<RuntimeProperties><Actions /><Questions /></RuntimeProperties></Properties>'
        '</AlteryxDocument>',
        encoding="utf-8",
    )

    engine_outer = f'<EngineSettings Macro="{outer}" />'
    caller = tmp_path / "caller.yxmd"
    caller.write_text(
        '<?xml version="1.0"?><AlteryxDocument yxmdVer="2022.1"><Nodes>'
        + _macro_node(
            "10",
            "AlteryxBasePluginsGui.TextInput.TextInput",
            "54",
            '<NumRows value="3" /><Fields><Field name="A" /></Fields><Data>'
            '<r><c>1</c></r><r><c>2</c></r><r><c>3</c></r></Data>',
            '<EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxTextInput" />',
        )
        + _macro_node("11", "outer.yxmc", "250", "", engine_outer)
        + '</Nodes>'
        '<Connections><Connection><Origin ToolID="10" Connection="Output" />'
        '<Destination ToolID="11" Connection="Input" /></Connection></Connections>'
        '<Properties><Memory default="True" /><GlobalRecordLimit value="0" />'
        '<RuntimeProperties><Actions /><Questions /></RuntimeProperties></Properties>'
        '</AlteryxDocument>',
        encoding="utf-8",
    )
    workflow = XmlWorkflowParser().parse(caller)
    result = run_workflow_graph(workflow, WorkflowContext(), target_node_ids={"11"})
    outputs = result.node_results["11"].outputs
    frame = next(iter(outputs.values()))
    assert len(frame.index) == 1
