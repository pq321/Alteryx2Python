import pandas as pd
import pytest

from alteryx2python.ir.models import EdgeIR, NodeIR, WorkflowIR
from alteryx2python.runtime.executor import run_tool_node, run_workflow_graph
from alteryx2python.tools.registry import TOOL_REGISTRY


def _workflow(nodes, edges):
    return WorkflowIR(
        workflow_id="contract-workflow",
        workflow_name="contract-workflow",
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


def test_run_tool_node_emits_select_contract_evidence(sample_frame, workflow_context):
    result = run_tool_node(
        TOOL_REGISTRY.get("Select"),
        inputs={"Input": sample_frame},
        config={
            "node_id": "select",
            "select_fields": [
                {"source": "account", "rename": "customer"},
                {"source": "amount"},
            ],
        },
        context=workflow_context,
    )

    evidence = result.contract_evidence

    assert evidence is not None
    assert evidence.passed
    assert evidence.output_schemas["Output"]["columns"] == ["customer", "amount"]
    assert evidence.output_schemas["Output"]["row_count"] == 3
    assert {
        (assertion.assertion_type, assertion.target)
        for assertion in evidence.assertions
        if assertion.passed
    } >= {
        ("anchor_emitted", "Output"),
        ("output_is_dataframe", "Output"),
        ("column_order_equals", "Output"),
        ("row_count_equals_input", "Output"),
    }


def test_expected_output_schema_mismatch_fails_fast(sample_frame, workflow_context):
    workflow = _workflow(
        nodes=[
            _node(
                "select",
                "Select",
                {
                    "select_fields": [{"source": "account"}],
                    "enforce_expected_output_schema": True,
                },
                expected_output_schema={
                    "fields": [
                        {"name": "account"},
                        {"name": "missing"},
                    ]
                },
            )
        ],
        edges=[],
    )

    with pytest.raises(AssertionError, match="columns must match expected schema"):
        run_workflow_graph(
            workflow,
            workflow_context,
            initial_inputs={"select": {"Input": sample_frame}},
        )


def test_filter_contract_evidence_asserts_partitioned_row_count(workflow_context):
    frame = pd.DataFrame({"account": ["A1", "A2", "A3"], "amount": [10, 20, 30]})
    result = run_tool_node(
        TOOL_REGISTRY.get("Filter"),
        inputs={"Input": frame},
        config={"node_id": "filter", "expression": "[amount] >= 20"},
        context=workflow_context,
    )

    evidence = result.contract_evidence

    assert evidence is not None
    assert evidence.passed
    partition_assertion = next(
        assertion
        for assertion in evidence.assertions
        if assertion.assertion_type == "row_count_equals_sum_of_anchors"
    )
    assert partition_assertion.expected == 3
    assert partition_assertion.actual == 3


def test_workflow_graph_records_contract_evidence_for_each_node(workflow_context):
    workflow = _workflow(
        nodes=[
            _node("source", "Select", {"select_fields": [{"source": "account"}, {"source": "amount"}]}),
            _node("formula", "Formula", {"formula_fields": [{"field": "double_amount", "expression": "[amount] * 2"}]}),
        ],
        edges=[_edge("source", "Output", "formula")],
    )

    result = run_workflow_graph(
        workflow,
        workflow_context,
        initial_inputs={
            "source": {
                "Input": pd.DataFrame({"account": ["A1", "A2"], "amount": [10, 20]})
            }
        },
    )

    assert result.node_results["source"].contract_evidence is not None
    formula_evidence = result.node_results["formula"].contract_evidence
    assert formula_evidence is not None
    assert formula_evidence.passed
    assert formula_evidence.output_schemas["Output"]["columns"] == [
        "account",
        "amount",
        "double_amount",
    ]


def test_union_contract_evidence_asserts_schema_and_row_count(workflow_context):
    workflow = _workflow(
        nodes=[
            _node("left", "Select", {"select_fields": [{"source": "a"}]}),
            _node("right", "Select", {"select_fields": [{"source": "b"}]}),
            _node("union", "Union", {"mode": "ByName"}),
        ],
        edges=[
            _edge("left", "Output", "union"),
            _edge("right", "Output", "union"),
        ],
    )

    result = run_workflow_graph(
        workflow,
        workflow_context,
        initial_inputs={
            "left": {"Input": pd.DataFrame({"a": [1, 2]})},
            "right": {"Input": pd.DataFrame({"b": [3]})},
        },
    )

    evidence = result.node_results["union"].contract_evidence

    assert evidence is not None
    assert evidence.passed
    assert evidence.output_schemas["Output"]["columns"] == ["a", "b"]
    row_count_assertion = next(
        assertion
        for assertion in evidence.assertions
        if assertion.assertion_type == "row_count_equals_sum_of_inputs"
    )
    assert row_count_assertion.expected == 3
    assert row_count_assertion.actual == 3


def test_union_by_pos_contract_uses_first_input_schema(workflow_context):
    workflow = _workflow(
        nodes=[
            _node("left", "Select", {"select_fields": [{"source": "a"}]}),
            _node("right", "Select", {"select_fields": [{"source": "b"}]}),
            _node("union", "Union", {"mode": "ByPos"}),
        ],
        edges=[
            _edge("left", "Output", "union"),
            _edge("right", "Output", "union"),
        ],
    )

    result = run_workflow_graph(
        workflow,
        workflow_context,
        initial_inputs={
            "left": {"Input": pd.DataFrame({"a": [1]})},
            "right": {"Input": pd.DataFrame({"b": [2]})},
        },
    )

    evidence = result.node_results["union"].contract_evidence

    assert evidence is not None
    assert evidence.passed
    assert evidence.output_schemas["Output"]["columns"] == ["a"]


def test_join_contract_evidence_asserts_anchors_and_unjoined_row_counts(workflow_context):
    workflow = _workflow(
        nodes=[
            _node(
                "join",
                "Join",
                {
                    "joins": [
                        {"connection": "Left", "field": "id"},
                        {"connection": "Right", "field": "id"},
                    ]
                },
            )
        ],
        edges=[],
    )

    result = run_workflow_graph(
        workflow,
        workflow_context,
        initial_inputs={
            "join": {
                "Left": pd.DataFrame({"id": [1, 2], "left_value": ["A", "B"]}),
                "Right": pd.DataFrame({"id": [2, 3], "right_value": ["C", "D"]}),
            }
        },
    )

    evidence = result.node_results["join"].contract_evidence

    assert evidence is not None
    assert evidence.passed
    assert evidence.output_schemas["Join"]["columns"] == [
        "Left_id",
        "Left_left_value",
        "Right_id",
        "Right_right_value",
    ]
    assert {
        (assertion.assertion_type, assertion.target)
        for assertion in evidence.assertions
        if assertion.passed
    } >= {
        ("anchor_emitted", "Join"),
        ("anchor_emitted", "Left"),
        ("anchor_emitted", "Right"),
        ("row_count_less_than_or_equal_input", "Left"),
        ("row_count_less_than_or_equal_input", "Right"),
    }
