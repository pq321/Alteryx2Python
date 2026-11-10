from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph


def _node(tool_id, kind, config):
    return f'<Node ToolID="{tool_id}"><GuiSettings Plugin="AlteryxBasePluginsGui.{kind}.{kind}"/><Properties><Configuration>{config}</Configuration></Properties></Node>'


def _edge(a, b, out="Output"):
    return f'<Connection><Origin ToolID="{a}" Connection="{out}"/><Destination ToolID="{b}" Connection="Input"/></Connection>'


def _outer(tmp_path, macro, value=""):
    source = tmp_path / "outer.yxmd"
    source.write_text(
        f'<AlteryxDocument><Nodes><Node ToolID="10"><GuiSettings/><Properties><Configuration>{value}</Configuration></Properties><EngineSettings Macro="{macro}"/></Node></Nodes></AlteryxDocument>',
        encoding="utf-8",
    )
    return XmlWorkflowParser().parse(source)


def _factor_macro(tmp_path, batch=False):
    question = "ControlParam" if batch else "NumericUpDown"
    xml = (
        "<AlteryxDocument><Nodes>"
        + _node("1", "MacroInput", "<Name>Input</Name>")
        + _node(
            "2",
            "Formula",
            '<FormulaFields><FormulaField field="y" expression="[x] * FACTOR" type="Double"/></FormulaFields>',
        )
        + _node("3", "MacroOutput", "<Name>Output</Name>")
        + "</Nodes><Connections>"
        + _edge("1", "2")
        + _edge("2", "3")
        + "</Connections>"
    )
    xml += f"""<Properties><RuntimeProperties><ModuleType>Macro</ModuleType><Questions><Question><Type>{question}</Type><Name>factor</Name><Default>2</Default></Question></Questions><Actions><NoCondition><True><Action><Type>UpdateValue</Type><Variable>factor</Variable><Replace value="True"/><ReplaceText>FACTOR</ReplaceText><Destination>2/FormulaFields/FormulaField/@expression</Destination></Action></True></NoCondition></Actions>"""
    if batch:
        xml += "<BatchMacro><OutputMode>AllSame</OutputMode></BatchMacro>"
    xml += "</RuntimeProperties></Properties></AlteryxDocument>"
    path = tmp_path / "Factor.yxmc"
    path.write_text(xml, encoding="utf-8")
    return path


def test_configured_standard_macro_uses_caller_value(tmp_path):
    macro = _factor_macro(tmp_path)
    workflow = _outer(tmp_path, macro.name, '<Value name="factor">4</Value>')
    result = run_workflow_graph(
        workflow,
        WorkflowContext(),
        initial_inputs={"10": {"Input": pd.DataFrame({"x": [1, 3]})}},
    )
    assert result.node_results["10"].outputs["Output"]["y"].tolist() == [4, 12]
    assert "FACTOR" in macro.read_text(encoding="utf-8")
    from alteryx2python.generator.python_generator import PythonGenerator

    namespace = {}
    exec(PythonGenerator().generate(workflow), namespace)
    macro.unlink()
    Path(workflow.source_file).unlink()
    result, _ = namespace["run_workflow"](
        initial_inputs={"10": {"Input": pd.DataFrame({"x": [2, 4]})}}
    )
    assert result.node_results["10"].outputs["Output"]["y"].tolist() == [8, 16]


def test_generated_python_embeds_nested_macro_sources(tmp_path):
    from alteryx2python.generator.python_generator import PythonGenerator

    child = _factor_macro(tmp_path)
    wrapper = tmp_path / "Wrapper.yxmc"
    wrapper.write_text(
        "<AlteryxDocument><Nodes>"
        + _node("1", "MacroInput", "<Name>Input</Name>")
        + '<Node ToolID="2"><GuiSettings/><Properties><Configuration><Value name="factor">4</Value></Configuration></Properties><EngineSettings Macro="Factor.yxmc"/></Node>'
        + _node("3", "MacroOutput", "<Name>Output</Name>")
        + "</Nodes><Connections>"
        + _edge("1", "2")
        + _edge("2", "3")
        + "</Connections></AlteryxDocument>",
        encoding="utf-8",
    )
    workflow = _outer(tmp_path, wrapper.name)
    namespace = {}
    exec(PythonGenerator().generate(workflow), namespace)
    child.unlink()
    wrapper.unlink()
    Path(workflow.source_file).unlink()
    result, _ = namespace["run_workflow"](
        initial_inputs={"10": {"Input": pd.DataFrame({"x": [3]})}}
    )
    assert result.node_results["10"].outputs["Output"]["y"].tolist() == [12]


def test_batch_reconfigures_each_control_record_without_mixing_inputs(tmp_path):
    macro = _factor_macro(tmp_path, batch=True)
    workflow = _outer(tmp_path, macro.name, '<Value name="factor">coeff</Value>')
    result = run_workflow_graph(
        workflow,
        WorkflowContext(),
        initial_inputs={
            "10": {
                "Input": pd.DataFrame({"x": [1, 3]}),
                "factor": pd.DataFrame({"coeff": [2, 5]}),
            }
        },
    )
    assert result.node_results["10"].outputs["Output"]["y"].tolist() == [2, 6, 5, 15]


def test_native_proof_rejects_changed_macro_dependencies(tmp_path):
    from alteryx2python.parity.runner import prepare, verify_manifest

    macro = _factor_macro(tmp_path)
    workflow = _outer(tmp_path, macro.name)
    directory = tmp_path / "evidence"
    prepare(Path(workflow.source_file), directory)
    macro.write_text(
        macro.read_text(encoding="utf-8").replace("FACTOR", "OTHER"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Macro dependency changed"):
        verify_manifest(directory)


def test_empty_batch_uses_declared_boundary_schema_without_executing_data(tmp_path):
    macro = _factor_macro(tmp_path, batch=True)
    root = ET.parse(macro).getroot()
    props = root.find(".//Node[@ToolID='3']/Properties")
    props.append(
        ET.fromstring(
            '<MetaInfo connection="Output"><RecordInfo><Field name="x" type="Int64"/><Field name="y" type="Double"/></RecordInfo></MetaInfo>'
        )
    )
    ET.ElementTree(root).write(macro, encoding="utf-8")
    workflow = _outer(tmp_path, macro.name, '<Value name="factor">coeff</Value>')
    context = WorkflowContext()
    result = run_workflow_graph(
        workflow,
        context,
        initial_inputs={
            "10": {
                "Input": pd.DataFrame({"x": [1, 3]}),
                "factor": pd.DataFrame({"coeff": []}),
            }
        },
    )
    output = result.node_results["10"].outputs["Output"]
    assert output.empty and list(output.columns) == ["x", "y"]
    assert context.traces[-1].config["child_execution_orders"] == []


def test_iterative_macro_repeats_feedback_until_empty(tmp_path):
    xml = (
        "<AlteryxDocument><Nodes>"
        + _node("1", "MacroInput", "<Name>Input</Name>")
        + _node(
            "2",
            "Formula",
            '<FormulaFields><FormulaField field="x" expression="[x] - 1" type="Int64"/></FormulaFields>',
        )
        + _node("3", "Filter", "<Mode>Custom</Mode><Expression>[x] &gt; 0</Expression>")
        + _node("4", "MacroOutput", "<Name>Loop</Name>")
        + _node("5", "MacroOutput", "<Name>Done</Name>")
        + "</Nodes><Connections>"
        + _edge("1", "2")
        + _edge("2", "3")
        + _edge("3", "4", "True")
        + _edge("3", "5", "False")
        + '</Connections><Properties><RuntimeProperties><ModuleType>Macro</ModuleType><IterativeMacro><Input>Input</Input><Output>Loop</Output><IterationLimit value="5"/><LimitBehavior>Error</LimitBehavior></IterativeMacro></RuntimeProperties></Properties></AlteryxDocument>'
    )
    macro = tmp_path / "Countdown.yxmc"
    macro.write_text(xml, encoding="utf-8")
    workflow = _outer(tmp_path, macro.name)
    context = WorkflowContext()
    result = run_workflow_graph(
        workflow, context, initial_inputs={"10": {"Input": pd.DataFrame({"x": [2, 3]})}}
    )
    assert result.node_results["10"].outputs["Done"]["x"].tolist() == [0, 0]
    assert len(context.traces[-1].config["child_execution_orders"]) == 3
