from pathlib import Path

from alteryx2python.ir.validators import validate_workflow_ir
from alteryx2python.parser.xml_parser import XmlWorkflowParser


def _write_workflow(tmp_path: Path, name: str, body: str) -> Path:
    source_path = tmp_path / name
    source_path.write_text(body, encoding="utf-8")
    return source_path


def test_xml_parser_extracts_nodes_edges_and_tool_config(tmp_path: Path):
    source_path = _write_workflow(
        tmp_path,
        "simple.yxmd",
        """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2024.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput" />
      <Properties>
        <Configuration>
          <File>input.csv</File>
        </Configuration>
        <MetaInfo connection="Output">
          <RecordInfo>
            <Field name="account" type="V_String" size="32" />
            <Field name="amount" type="Double" />
          </RecordInfo>
        </MetaInfo>
      </Properties>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect" />
      <Properties>
        <Configuration>
          <SelectFields>
            <SelectField field="account" selected="True" />
          </SelectFields>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections>
    <Connection>
      <Origin ToolID="1" Connection="Output" />
      <Destination ToolID="2" Connection="Input" />
    </Connection>
  </Connections>
</AlteryxDocument>
""",
    )

    workflow = XmlWorkflowParser().parse(source_path)

    assert workflow.workflow_name == "simple"
    assert len(workflow.nodes) == 2
    assert len(workflow.edges) == 1
    assert workflow.external_dependencies == ["input.csv"]
    assert workflow.warnings == []

    input_node = workflow.nodes[0]
    assert input_node.node_id == "1"
    assert input_node.source_tool_id == "1"
    assert input_node.tool_type == "DbFileInput"
    assert input_node.tool_name == "AlteryxBasePluginsGui.DbFileInput.DbFileInput"
    assert input_node.config["raw"]["File"]["text"] == "input.csv"
    assert input_node.output_anchors[0].name == "Output"
    assert input_node.expected_output_schema["fields"][0]["name"] == "account"
    assert input_node.outgoing_edges == ["1:Output->2:Input"]

    select_node = workflow.nodes[1]
    assert select_node.input_anchors[0].name == "Input"
    assert select_node.incoming_edges == ["1:Output->2:Input"]

    edge = workflow.edges[0]
    assert edge.edge_id == "1:Output->2:Input"
    assert edge.source_node_id == "1"
    assert edge.target_node_id == "2"
    assert edge.source_anchor == "Output"
    assert edge.target_anchor == "Input"

    assert validate_workflow_ir(workflow) == []


def test_xml_parser_extracts_tool_container_children(tmp_path: Path):
    source_path = _write_workflow(
        tmp_path,
        "container.yxmd",
        """<?xml version="1.0"?>
<AlteryxDocument>
  <Nodes>
    <Node ToolID="39">
      <GuiSettings Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer" />
      <Properties>
        <Configuration>
          <Caption>Example Container</Caption>
          <Disabled value="True" />
        </Configuration>
      </Properties>
      <ChildNodes>
        <Node ToolID="18">
          <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput" />
          <Properties>
            <Configuration>
              <File>child.csv</File>
            </Configuration>
          </Properties>
        </Node>
      </ChildNodes>
    </Node>
  </Nodes>
</AlteryxDocument>
""",
    )

    workflow = XmlWorkflowParser().parse(source_path)

    assert len(workflow.nodes) == 2
    container_node = workflow.nodes[0]
    child_node = workflow.nodes[1]

    assert container_node.tool_type == "ToolContainer"
    assert container_node.supported_status == "L1_CONTAINER_ONLY"
    assert container_node.config["raw"]["Caption"]["text"] == "Example Container"
    assert container_node.config["raw"]["child_node_ids"] == ["18"]
    assert child_node.config["raw"]["container_id"] == "39"
    assert workflow.external_dependencies == ["child.csv"]


def test_xml_parser_marks_interface_and_action_nodes_as_deferred(tmp_path: Path):
    source_path = _write_workflow(
        tmp_path,
        "ui_nodes.yxmd",
        """<?xml version="1.0"?>
<AlteryxDocument>
  <Nodes>
    <Node ToolID="10">
      <GuiSettings Plugin="AlteryxGuiToolkit.Questions.FileBrowse.FileBrowse" />
      <Properties>
        <Configuration />
      </Properties>
    </Node>
    <Node ToolID="11">
      <GuiSettings Plugin="AlteryxGuiToolkit.Action.Action" />
      <Properties>
        <Configuration />
      </Properties>
    </Node>
  </Nodes>
</AlteryxDocument>
""",
    )

    workflow = XmlWorkflowParser().parse(source_path)

    assert [node.supported_status for node in workflow.nodes] == [
        "L0_DEFERRED_INTERFACE_NODE",
        "L0_DEFERRED_ACTION_NODE",
    ]
    assert any("interface node" in warning.lower() for warning in workflow.warnings)
    assert any("action node" in warning.lower() for warning in workflow.warnings)


def test_xml_parser_extracts_real_workflow_snapshot():
    parser = XmlWorkflowParser()
    source_path = Path(__file__).resolve().parents[2] / "examples" / "sample_workflows" / "MIFID II.yxwz"

    workflow = parser.parse(source_path)

    assert workflow.workflow_name == "MIFID II"
    assert len(workflow.nodes) == 43
    assert len(workflow.edges) == 40
    assert len(workflow.external_dependencies) == 4
    assert any(node.tool_type == "ToolContainer" for node in workflow.nodes)
    assert any(node.tool_type == "DbFileInput" for node in workflow.nodes)
    assert any(node.tool_type == "Formula" for node in workflow.nodes)
    assert any(node.tool_type == "Action" for node in workflow.nodes)
    assert any(node.tool_type == "QuestionFileBrowse" for node in workflow.nodes)
    assert validate_workflow_ir(workflow) == []
