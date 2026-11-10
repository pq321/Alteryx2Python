import json
from xml.etree import ElementTree as ET

import pytest

from alteryx2python.workflow_spec import (
    WorkflowSpec,
    NodeSpec,
    EdgeSpec,
    load_workflow_spec,
)
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph


def graph():
    return WorkflowSpec(
        [
            NodeSpec(
                "1",
                "TextInput",
                '<Fields><Field name="x"/></Fields><Data><r><c>1</c></r><r><c>3</c></r></Data>',
            ),
            NodeSpec(
                "2", "Filter", "<Expression>[x] &gt; 1</Expression><Mode>Custom</Mode>"
            ),
            NodeSpec(
                "3",
                "Formula",
                '<FormulaFields><FormulaField field="twice" type="Int64" expression="[x] * 2"/></FormulaFields>',
            ),
        ],
        [EdgeSpec("1", "2"), EdgeSpec("2", "3", "True")],
    )


def test_catalog_bindings_and_generated_branch_runs():
    spec = WorkflowSpec.from_json(json.loads(graph().to_json()))
    root = ET.fromstring(spec.to_xml())
    assert (
        root.find("./Nodes/Node/GuiSettings").get("Plugin")
        == "AlteryxBasePluginsGui.TextInput.TextInput"
    )
    assert (
        root.find("./Nodes/Node/EngineSettings").get("EngineDllEntryPoint")
        == "AlteryxTextInput"
    )
    assert (
        root.find("./Nodes/Node[@ToolID='3']/EngineSettings").get("EngineDllEntryPoint")
        == "AlteryxFormula"
    )
    workflow = XmlWorkflowParser().parse_xml(
        spec.to_xml(), __import__("pathlib").Path("spec.yxmd")
    )
    result = run_workflow_graph(workflow, WorkflowContext())
    assert result.node_results["2"].outputs["False"]["x"].tolist() == [1]
    assert result.node_results["3"].outputs["Output"]["twice"].tolist() == [6]


def test_invalid_anchors_cycles_and_duplicate_ids_fail():
    spec = graph()
    spec.edges[0].source_anchor = "Typo"
    with pytest.raises(ValueError, match="anchor"):
        spec.validate()
    spec = graph()
    spec.edges.append(EdgeSpec("3", "2"))
    with pytest.raises(ValueError, match="cycle"):
        spec.validate()
    spec = graph()
    spec.nodes.append(spec.nodes[0])
    with pytest.raises(ValueError, match="duplicate"):
        spec.validate()


def test_import_export_and_edit_preserve_unknown_xml(tmp_path):
    source = tmp_path / "original.yxmd"
    root = ET.fromstring(graph().to_xml())
    root.set("UserAttribute", "preserve")
    ET.SubElement(
        root.find("Properties"), "UnknownProperty", {"setting": "keep"}
    ).text = "value"
    ET.SubElement(
        root.find("Nodes/Node/Properties"), "UnknownNodeProperty"
    ).text = "data"
    source.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
    exported = WorkflowSpec.from_json(load_workflow_spec(source).to_json())
    exported.nodes.append(
        NodeSpec(
            "4", "Sort", '<SortInfo><Field field="x" order="Ascending"/></SortInfo>'
        )
    )
    exported.edges.append(EdgeSpec("3", "4"))
    edited = ET.fromstring(exported.to_xml())
    assert edited.get("UserAttribute") == "preserve"
    assert edited.findtext("Properties/UnknownProperty") == "value"
    assert edited.findtext("Nodes/Node/Properties/UnknownNodeProperty") == "data"
    assert edited.find("./Nodes/Node[@ToolID='4']") is not None
    assert len(edited.findall(".//Configuration/Configuration")) == 0


def test_custom_macro_binding_and_unknown_tool_fail_closed():
    spec = WorkflowSpec(
        [
            NodeSpec(
                "1",
                "Macro_Mine",
                macro_path="Mine.yxmc",
                input_anchors=("Input",),
                output_anchors=("Output",),
            )
        ]
    )
    assert (
        ET.fromstring(spec.to_xml()).find("Nodes/Node/EngineSettings").get("Macro")
        == "Mine.yxmc"
    )
    with pytest.raises(ValueError, match="Unknown tool"):
        WorkflowSpec([NodeSpec("1", "Invented")]).to_xml()


def test_control_flag_cannot_hide_arbitrary_data_cycle():
    spec = graph()
    spec.edges.append(EdgeSpec("3", "2", control=True))
    with pytest.raises(ValueError, match="control"):
        spec.validate()


def test_legacy_builder_quotes_formula_attributes_and_correct_engine_bindings():
    from alteryx2python.workflow_generator import WorkflowBuilder

    builder = WorkflowBuilder()
    builder.add_formula([('field"quote', "V_WString", "40", '"hello"')])
    root = ET.fromstring(builder.render())
    formula = root.find(".//FormulaField")
    assert (
        formula.get("field") == 'field"quote' and formula.get("expression") == '"hello"'
    )
    from alteryx2python.workflow_generator import _entry

    assert _entry("RegEx") == "AlteryxRegEx"
    assert _entry("CrossTab") == "AlteryxCrossTab"


def test_relocation_keeps_relative_input_resource_bound_to_original_directory(tmp_path):
    original_dir = tmp_path / "original"
    original_dir.mkdir()
    (original_dir / "data.csv").write_text("x\n7\n", encoding="utf-8")
    workflow = original_dir / "workflow.yxmd"
    workflow.write_text(
        WorkflowSpec(
            [
                NodeSpec(
                    "1",
                    "DbFileInput",
                    '<File FileFormat="0">data.csv</File><FormatSpecificOptions><HeaderRow>True</HeaderRow></FormatSpecificOptions>',
                )
            ]
        ).to_xml(),
        encoding="utf-8",
    )
    exported = WorkflowSpec.from_json(load_workflow_spec(workflow).to_json())
    relocated = tmp_path / "other" / "moved.yxmd"
    relocated.parent.mkdir()
    relocated.write_text(exported.to_xml(), encoding="utf-8")
    assert ET.parse(relocated).find(".//File").text == str(original_dir / "data.csv")
    result = run_workflow_graph(XmlWorkflowParser().parse(relocated), WorkflowContext())
    assert result.node_results["1"].outputs["Output"]["x"].tolist() == [7]
