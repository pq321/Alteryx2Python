from pathlib import Path

from alteryx2python.ir.validators import validate_workflow_ir
from alteryx2python.parser.xml_parser import XmlWorkflowParser


REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_WORKFLOW_PATH = REPO_ROOT / "examples" / "sample_workflows" / "MIFID II.yxwz"


def test_real_workflow_fixture_exists():
    assert REAL_WORKFLOW_PATH.exists()
    assert REAL_WORKFLOW_PATH.is_file()


def test_real_workflow_can_be_loaded_by_current_xml_parser():
    parser = XmlWorkflowParser()

    workflow = parser.parse(REAL_WORKFLOW_PATH)

    assert workflow.workflow_name == "MIFID II"
    assert workflow.source_file.endswith("MIFID II.yxwz")
    assert workflow.source_hash
    assert workflow.classification == "CLASS_D_PARTIAL_MIGRATION_ONLY"
    assert len(workflow.nodes) == 43
    assert len(workflow.edges) == 40
    assert any("Deferred interface node" in warning for warning in workflow.warnings)
    assert any("Deferred action node" in warning for warning in workflow.warnings)
    select_nodes = [node for node in workflow.nodes if node.tool_type == "Select"]
    assert select_nodes
    assert "select_fields" in select_nodes[0].config["normalized"]
    db_input_nodes = [node for node in workflow.nodes if node.tool_type == "DbFileInput"]
    assert db_input_nodes
    assert "file" in db_input_nodes[0].config["normalized"]
    assert validate_workflow_ir(workflow) == []
