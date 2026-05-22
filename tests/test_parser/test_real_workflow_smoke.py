from pathlib import Path

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
    assert workflow.warnings == ["XML parsed but node/tool extraction is not implemented yet."]
