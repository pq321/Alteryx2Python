from pathlib import Path

import pandas as pd

from alteryx2python.certification import assert_nodes_certifiable
from alteryx2python.comparison.dataframe_diff import compare_dataframes
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph


WORKFLOW = Path("examples/sample_workflows/MIFID II.yxwz")
FIXTURE = Path("tests/fixtures/real_workflows/mifid_download_data.csv")
MAPPING_FIXTURE = Path("tests/fixtures/real_workflows/mifid_mapping.csv")
EXPECTED_TARGET36 = Path("tests/fixtures/real_workflows/mifid_target36_expected.csv")
TEXT_INPUT_WORKFLOW = Path("D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/01 In Out/Text_Input.yxmd")
EXPECTED_TEXT_INPUT = Path("tests/fixtures/real_workflows/text_input_expected.csv")
COMBINE_CUSTOMER_WORKFLOW = Path(
    "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd"
)
EXPECTED_COMBINE_CUSTOMER = Path("tests/fixtures/real_workflows/combine_customer_profile_expected.csv")


def test_mifid_first_supported_subgraph_executes_from_real_parsed_workflow():
    workflow = XmlWorkflowParser().parse(WORKFLOW)
    node18 = next(node for node in workflow.nodes if node.node_id == "18")
    node18.config["normalized"] = {
        **node18.config["normalized"],
        "file": str(FIXTURE),
        "file_attributes": {"FileFormat": "0", "RecordLimit": "", "SearchSubDirs": "False"},
        "format_specific_options": {
            "HeaderRow": {"text": "True"},
            "ImportLine": {"text": "1"},
            "Delimeter": {"text": ","},
            "CodePage": {"text": "28591"},
        },
    }
    context = WorkflowContext(runtime_config={"skip_app_configuration": True})

    result = run_workflow_graph(workflow, context, target_node_ids={"24"})

    assert result.execution_order == ["18", "21", "22", "23", "24"]
    true_output = result.node_results["24"].outputs["True"]
    false_output = result.node_results["24"].outputs["False"]

    assert list(true_output.columns) == [
        "Trade ref",
        "regulation",
        "Trade Domain",
        "Trade ID",
        "Trade version",
        "JSON",
        "JSON_Name",
        "JSON_ValueString",
        "FieldKey",
    ]
    assert true_output[["JSON_Name", "JSON_ValueString"]].to_dict("records") == [
        {"JSON_Name": "result.exceptions.0.assetClass", "JSON_ValueString": "EQ"},
        {"JSON_Name": "result.exceptions.0.buyerId", "JSON_ValueString": "BUYER-1"},
    ]
    assert false_output["JSON_Name"].tolist() == ["status"]
    assert result.skipped_node_ids
    assert context.warnings == ["Skipped frontier node 25 (CrossTab) downstream of 24:True"]


def test_mifid_first_reshape_subgraph_executes_to_formula_node():
    workflow = XmlWorkflowParser().parse(WORKFLOW)
    node18 = next(node for node in workflow.nodes if node.node_id == "18")
    node18.config["normalized"] = {
        **node18.config["normalized"],
        "file": str(FIXTURE),
        "file_attributes": {"FileFormat": "0", "RecordLimit": "", "SearchSubDirs": "False"},
        "format_specific_options": {
            "HeaderRow": {"text": "True"},
            "ImportLine": {"text": "1"},
            "Delimeter": {"text": ","},
            "CodePage": {"text": "28591"},
        },
    }
    node32 = next(node for node in workflow.nodes if node.node_id == "32")
    node32.config["normalized"] = {
        **node32.config["normalized"],
        "file": str(MAPPING_FIXTURE),
    }

    result = run_workflow_graph(workflow, WorkflowContext(runtime_config={"skip_app_configuration": True}), target_node_ids={"36"})

    output = result.node_results["36"].outputs["Output"]
    assert set(result.execution_order) == {"18", "21", "22", "23", "24", "25", "27", "29", "28", "32", "33", "34", "36"}
    assert result.execution_order.index("18") < result.execution_order.index("21")
    assert result.execution_order.index("28") < result.execution_order.index("33")
    assert result.execution_order.index("32") < result.execution_order.index("33")
    assert result.execution_order.index("33") < result.execution_order.index("34")
    assert result.execution_order.index("34") < result.execution_order.index("36")
    assert output[["RecordID", "Value", "OutputOrder", "TargetField", "FinalValue", "OrderedTargetField"]].to_dict("records") == [
        {
            "RecordID": 1.0,
            "Value": "EQ",
            "OutputOrder": 1,
            "TargetField": "Asset_Class",
            "FinalValue": "EQ",
            "OrderedTargetField": "001_Asset_Class",
        },
        {
            "RecordID": 1.0,
            "Value": "BUYER-1",
            "OutputOrder": 2,
            "TargetField": "Buyer_ID",
            "FinalValue": "BUYER-1",
            "OrderedTargetField": "002_Buyer_ID",
        },
    ]
    assert result.warnings == ["Skipped frontier node 37 (CrossTab) downstream of 36:Output"]

    expected = pd.read_csv(EXPECTED_TARGET36).astype(object)
    actual = output[
        ["RecordID", "Value", "OutputOrder", "TargetField", "FinalValue", "OrderedTargetField"]
    ].astype(object)
    diff = compare_dataframes(
        actual,
        expected,
    )
    assert diff.matches, diff.issues


def test_official_text_input_workflow_executes_complete_data_output():
    workflow = XmlWorkflowParser().parse(TEXT_INPUT_WORKFLOW)

    result = run_workflow_graph(workflow, WorkflowContext(), target_node_ids={"98"})

    assert result.execution_order == ["98"]
    assert result.skipped_node_ids
    output = result.node_results["98"].outputs["Output"]
    # Native Text Input infers column dtypes from the embedded data, so the
    # oracle CSV is read with pandas type inference (not forced to strings).
    expected = pd.read_csv(EXPECTED_TEXT_INPUT, keep_default_na=False,
                           na_values={"LastName": [""]})  # Native XML <c/> is null.

    diff = compare_dataframes(output, expected)
    assert diff.matches, diff.issues


def test_official_basic_combine_customer_workflow_matches_alteryx_output(tmp_path):
    workflow = XmlWorkflowParser().parse(COMBINE_CUSTOMER_WORKFLOW)
    output_path = tmp_path / "Excel.CustomerProfileOutput.csv"
    output_node = next(node for node in workflow.nodes if node.node_id == "23")
    output_node.config["normalized"] = {
        **output_node.config["normalized"],
        "file": str(output_path),
    }

    result = run_workflow_graph(workflow, WorkflowContext(), target_node_ids={"23"})

    assert result.execution_order == ["1", "2", "7", "3", "4", "6", "23"]
    assert_nodes_certifiable(workflow, result.execution_order)
    assert output_path.read_bytes() == EXPECTED_COMBINE_CUSTOMER.read_bytes()
    actual = pd.read_csv(output_path, dtype=object, keep_default_na=False)
    expected = pd.read_csv(EXPECTED_COMBINE_CUSTOMER, dtype=object, keep_default_na=False)
    diff = compare_dataframes(actual, expected)
    assert diff.matches, diff.issues
