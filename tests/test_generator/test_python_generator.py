from pathlib import Path

import pandas as pd

from alteryx2python.certification import assert_nodes_certifiable
from alteryx2python.comparison.dataframe_diff import compare_dataframes
from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.ir.models import EdgeIR, NodeIR, WorkflowIR
from alteryx2python.parser.xml_parser import XmlWorkflowParser


def _workflow(nodes, edges):
    return WorkflowIR(
        workflow_id="generated-test",
        workflow_name="generated-test",
        source_file="synthetic",
        source_hash="hash",
        parser_version="0.1.0",
        migration_spec_version="0.1.0",
        nodes=nodes,
        edges=edges,
    )


def _node(node_id, tool_type, config, expected_output_schema=None):
    return NodeIR(
        node_id=node_id,
        source_tool_id=node_id,
        tool_type=tool_type,
        tool_name=tool_type,
        config={"normalized": config},
        expected_output_schema=expected_output_schema or {},
        supported_status="L2_BASIC_IMPLEMENTATION",
    )


def _edge(source, source_anchor, target, target_anchor="Input"):
    return EdgeIR(
        edge_id=f"{source}:{source_anchor}->{target}:{target_anchor}",
        source_node_id=source,
        source_anchor=source_anchor,
        target_node_id=target,
        target_anchor=target_anchor,
    )


def test_python_generator_emits_runtime_imports_and_node_ids():
    workflow = _workflow(
        [_node("1", "Select", {"select_fields": [{"source": "account"}]})],
        [],
    )

    code = PythonGenerator().generate(workflow)

    assert "from alteryx2python.runtime.executor import run_workflow_graph" in code
    assert "'node_id': '1'" in code
    assert "def run_workflow(runtime_config=None, initial_inputs=None, target_node_ids=None):" in code


def test_python_generator_preserves_expected_output_schema():
    workflow = _workflow(
        [
            _node(
                "union",
                "Union",
                {"mode": "ByPos"},
                expected_output_schema={"fields": [{"name": "Concat_Field1"}]},
            )
        ],
        [],
    )
    namespace = {}
    exec(PythonGenerator().generate(workflow), namespace)

    node = namespace["build_workflow"]().nodes[0]

    assert node.expected_output_schema == {"fields": [{"name": "Concat_Field1"}]}


def test_generated_code_executes_synthetic_workflow_roundtrip():
    workflow = _workflow(
        [
            _node("select", "Select", {"select_fields": [{"source": "amount"}]}),
            _node("formula", "Formula", {"formula_fields": [{"field": "double", "expression": "[amount] * 2"}]}),
        ],
        [_edge("select", "Output", "formula")],
    )
    namespace = {}
    exec(PythonGenerator().generate(workflow), namespace)

    result, report = namespace["run_workflow"](
        runtime_config={"mode": "generated"},
        initial_inputs={"select": {"Input": pd.DataFrame({"amount": [2, 3]})}},
    )

    assert result.execution_order == ["select", "formula"]
    assert result.node_results["formula"].outputs["Output"].to_dict("records") == [
        {"amount": 2, "double": 4},
        {"amount": 3, "double": 6},
    ]
    assert report["runtime_config"] == {"mode": "generated"}


def test_generated_code_executes_real_mifid_slice_with_embedded_config():
    workflow = XmlWorkflowParser().parse(Path("examples/sample_workflows/MIFID II.yxwz"))
    node18 = next(node for node in workflow.nodes if node.node_id == "18")
    node18.config["normalized"] = {
        **node18.config["normalized"],
        "file": "tests/fixtures/real_workflows/mifid_download_data.csv",
        "file_attributes": {"FileFormat": "0", "RecordLimit": "", "SearchSubDirs": "False"},
        "format_specific_options": {
            "HeaderRow": {"text": "True"},
            "ImportLine": {"text": "1"},
            "Delimeter": {"text": ","},
            "CodePage": {"text": "28591"},
        },
    }
    namespace = {}
    exec(PythonGenerator().generate(workflow), namespace)

    result, _ = namespace["run_workflow"](runtime_config={"skip_app_configuration": True}, target_node_ids={"24"})

    assert result.execution_order == ["18", "21", "22", "23", "24"]
    assert result.node_results["24"].outputs["True"]["JSON_ValueString"].tolist() == ["EQ", "BUYER-1"]


def test_generated_code_executes_official_text_input_workflow_roundtrip():
    workflow = XmlWorkflowParser().parse(
        Path("D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/01 In Out/Text_Input.yxmd")
    )
    namespace = {}
    exec(PythonGenerator().generate(workflow), namespace)

    result, _ = namespace["run_workflow"](target_node_ids={"98"})

    # Native Text Input infers column dtypes; read the oracle with inference.
    expected = pd.read_csv(
        "tests/fixtures/real_workflows/text_input_expected.csv",
        keep_default_na=False,
        na_values={"LastName": [""]},  # Native empty Text Input cell is null.
    )
    actual = result.node_results["98"].outputs["Output"]
    diff = compare_dataframes(actual, expected)
    assert result.execution_order == ["98"]
    assert diff.matches, diff.issues


def test_generated_code_executes_official_basic_combine_customer_workflow(tmp_path):
    workflow = XmlWorkflowParser().parse(
        Path("D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd")
    )
    output_path = tmp_path / "Excel.CustomerProfileOutput.csv"
    output_node = next(node for node in workflow.nodes if node.node_id == "23")
    output_node.config["normalized"] = {
        **output_node.config["normalized"],
        "file": str(output_path),
    }
    namespace = {}
    exec(PythonGenerator().generate(workflow), namespace)

    result, _ = namespace["run_workflow"](target_node_ids={"23"})

    actual = pd.read_csv(output_path, dtype=object, keep_default_na=False)
    expected = pd.read_csv(
        "tests/fixtures/real_workflows/combine_customer_profile_expected.csv",
        dtype=object,
        keep_default_na=False,
    )
    diff = compare_dataframes(actual, expected)
    assert result.execution_order == ["1", "2", "7", "3", "4", "6", "23"]
    assert_nodes_certifiable(workflow, result.execution_order)
    assert output_path.read_bytes() == Path(
        "tests/fixtures/real_workflows/combine_customer_profile_expected.csv"
    ).read_bytes()
    assert diff.matches, diff.issues
