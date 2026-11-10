from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from alteryx2python.runtime.app_config import configure_workflow, question_manifest
from alteryx2python.workflow_spec import WorkflowSpec, NodeSpec, EdgeSpec
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.generator.python_generator import PythonGenerator


def app_xml():
    spec = WorkflowSpec(
        [
            NodeSpec(
                "1",
                "TextInput",
                '<Fields><Field name="x"/></Fields><Data><r><c>2</c></r><r><c>5</c></r></Data>',
            ),
            NodeSpec(
                "2",
                "Formula",
                '<FormulaFields><FormulaField field="result" expression="[x] * FACTOR" type="Int64"/></FormulaFields>',
            ),
            NodeSpec(
                "3",
                "NumericUpDown",
                template_xml='<Node ToolID="3"><GuiSettings Plugin="AlteryxGuiToolkit.Questions.NumericUpDown.NumericUpDown"/><Properties><Configuration/></Properties></Node>',
            ),
            NodeSpec(
                "4",
                "Action",
                template_xml='<Node ToolID="4"><GuiSettings Plugin="AlteryxGuiToolkit.Action.Action"/><Properties><Configuration/></Properties></Node>',
            ),
        ],
        [
            EdgeSpec("1", "2"),
            EdgeSpec("3", "4", "Question", "Question", True),
            EdgeSpec("4", "2", "Action", "Action", True),
        ],
        kind="yxwz",
    )
    root = ET.fromstring(spec.to_xml())
    runtime = root.find("Properties/RuntimeProperties")
    runtime.append(
        ET.fromstring(
            """<Questions><Question><Type>Tab</Type><Name>Tab</Name><Questions><Question><Type>NumericUpDown</Type><Name>factor</Name><ToolId value="3"/><Default value="2"/><Minimum value="1"/><Maximum value="10"/></Question></Questions></Question></Questions>"""
        )
    )
    runtime.append(
        ET.fromstring(
            """<Actions><NoCondition><Type>NoCondition</Type><True><Action><Type>UpdateValue</Type><Variable>factor</Variable><Replace value="True"/><ReplaceText>FACTOR</ReplaceText><Destination>2/FormulaFields/FormulaField/@expression</Destination></Action></True></NoCondition></Actions>"""
        )
    )
    return ET.tostring(root, encoding="unicode")


def test_native_question_changes_executed_formula_and_generated_python(tmp_path):
    source = tmp_path / "app.yxwz"
    source.write_text(app_xml(), encoding="utf-8")
    original = source.read_bytes()
    workflow = XmlWorkflowParser().parse(source)
    assert question_manifest(ET.fromstring(workflow.source_xml))[0].node_id == "3"
    context = WorkflowContext(runtime_config={"answers": {"factor": 3}})
    result = run_workflow_graph(workflow, context)
    assert result.execution_order == ["1", "2"]
    assert result.node_results["2"].outputs["Output"]["result"].tolist() == [6, 15]
    namespace = {}
    exec(PythonGenerator().generate(workflow), namespace)
    source.unlink()  # Generated code carries the source configuration, not a live path dependency.
    generated, _ = namespace["run_workflow"](runtime_config={"answers": {"3": 4}})
    assert generated.node_results["2"].outputs["Output"]["result"].tolist() == [8, 20]
    assert b"FACTOR" in original


def test_defaults_bounds_unknown_answers_and_missing_destinations():
    configured, bound = configure_workflow(app_xml())
    assert bound["factor"] == 2
    assert configured.find(".//FormulaField").get("expression") == "[x] * 2"
    workflow = XmlWorkflowParser().parse_xml(app_xml(), Path("default-app.yxwz"))
    target = run_workflow_graph(workflow, WorkflowContext(), target_node_ids={"2"})
    assert target.node_results["2"].outputs["Output"]["result"].tolist() == [4, 10]
    with pytest.raises(ValueError, match="bounds"):
        configure_workflow(app_xml(), {"factor": 11})
    with pytest.raises(ValueError, match="Unknown"):
        configure_workflow(app_xml(), {"typo": 3})
    broken = app_xml().replace(
        "2/FormulaFields/FormulaField/@expression", "99/NoSuchField"
    )
    with pytest.raises(ValueError, match="not found"):
        configure_workflow(broken)


def test_conditions_formula_and_raw_xml_actions():
    root = ET.fromstring(app_xml())
    actions = root.find("Properties/RuntimeProperties/Actions")
    actions.clear()
    actions.append(
        ET.fromstring(
            """<Condition><Expression>[factor] &gt; 2</Expression><True><Action><Type>UpdateValueFormula</Type><Expression>"[x] + 1"</Expression><Destination>2/FormulaFields/FormulaField/@expression</Destination></Action></True><False><Action><Type>UpdateRawXml</Type><Expression>'&lt;FormulaField field="result" expression="[x] - 1" type="Int64"/&gt;'</Expression><Destination>2/FormulaFields</Destination><OuterXml value="False"/></Action></False></Condition>"""
        )
    )
    configured, _ = configure_workflow(root, {"factor": 3})
    assert configured.find(".//FormulaField").get("expression") == "[x] + 1"
    configured, _ = configure_workflow(root, {"factor": 1})
    assert configured.find(".//FormulaField").get("expression") == "[x] - 1"


def test_installed_macro_questions_and_action_shape():
    source = Path("D:/Alteryx/bin/RuntimeData/Macros/SelectRecords.yxmc")
    if not source.exists():
        pytest.skip("Installed Alteryx sample unavailable")
    configured, values = configure_workflow(source, {"Ranges": "2-3"})
    assert values == {"Ranges": "2-3"}
    assert (
        configured.find(".//Node[@ToolID='3']/Properties/Configuration/Data/r/c").text
        == "2-3"
    )


def test_file_browse_updates_path_and_preserves_native_format():
    root = ET.fromstring(
        """<AlteryxDocument><Nodes><Node ToolID="1"><Properties><Configuration><File FileFormat="0">before.csv</File></Configuration></Properties></Node></Nodes><Properties><RuntimeProperties><Questions><Question><Type>FileBrowse</Type><Name>file</Name><Default>before.csv</Default></Question></Questions><Actions><NoCondition><True><Action><Type>UpdateInput</Type><Variable>file</Variable><InputTool value="1"/><Required value="True"/></Action></True></NoCondition></Actions></RuntimeProperties></Properties></AlteryxDocument>"""
    )
    configured, _ = configure_workflow(root, {"file": "after.csv"})
    assert configured.find(".//File").text == "after.csv"
    assert configured.find(".//File").get("FileFormat") == "0"
    with pytest.raises(NotImplementedError, match="format"):
        configure_workflow(root, {"file": "after.xlsx"})
