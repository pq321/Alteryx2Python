import pandas as pd
import pytest

from alteryx2python.ir.models import EdgeIR, NodeIR, WorkflowIR
from alteryx2python.runtime.executor import run_tool_node, run_workflow_graph
from alteryx2python.tools.registry import TOOL_REGISTRY


def test_executor_runs_registered_select_tool(sample_frame, workflow_context):
    metadata = TOOL_REGISTRY.get("Select")
    result = run_tool_node(
        metadata,
        inputs={"Input": sample_frame},
        config={"node_id": "select-1", "select_fields": [{"source": "account"}]},
        context=workflow_context,
    )

    assert result.node_id == "select-1"
    assert result.tool_type == "Select"
    assert list(result.outputs["Output"].columns) == ["account"]
    assert result.trace is not None


def _workflow(nodes, edges):
    return WorkflowIR(
        workflow_id="test-workflow",
        workflow_name="test-workflow",
        source_file="synthetic",
        source_hash="hash",
        parser_version="0.1.0",
        migration_spec_version="0.1.0",
        nodes=nodes,
        edges=edges,
    )


def _node(node_id, tool_type, config):
    return NodeIR(
        node_id=node_id,
        source_tool_id=node_id,
        tool_type=tool_type,
        tool_name=tool_type,
        config={"normalized": config},
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


def test_workflow_graph_executes_linear_pipeline_with_topological_order(workflow_context, tmp_path):
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("account,amount,flag\nA1,10,true\nA2,20,false\n", encoding="utf-8")
    workflow = _workflow(
        nodes=[
            _node(
                "1",
                "DbFileInput",
                {
                    "file": str(csv_path),
                    "file_attributes": {"FileFormat": "0"},
                    "format_specific_options": {"HeaderRow": {"attributes": {"value": "True"}}},
                },
            ),
            _node("2", "Select", {"select_fields": [{"source": "account"}, {"source": "amount"}]}),
            _node("3", "Formula", {"formula_fields": [{"field": "double_amount", "expression": "[amount] * 2"}]}),
        ],
        edges=[_edge("1", "Output", "2"), _edge("2", "Output", "3")],
    )

    result = run_workflow_graph(workflow, workflow_context)

    assert result.node_results["3"].outputs["Output"].to_dict("records") == [
        {"account": "A1", "amount": 10, "double_amount": 20},
        {"account": "A2", "amount": 20, "double_amount": 40},
    ]
    assert result.execution_order == ["1", "2", "3"]
    assert [trace.node_id for trace in workflow_context.traces] == ["1", "2", "3"]


def test_workflow_graph_routes_filter_true_and_false_anchors(workflow_context):
    input_frame = pd.DataFrame({"account": ["A1", "A2", "A3"], "amount": [10, 20, 30]})
    workflow = _workflow(
        nodes=[
            _node("filter", "Filter", {"expression": "[amount] >= 20"}),
            _node("true_select", "Select", {"select_fields": [{"source": "account"}]}),
            _node("false_select", "Select", {"select_fields": [{"source": "amount"}]}),
        ],
        edges=[
            _edge("filter", "True", "true_select"),
            _edge("filter", "False", "false_select"),
        ],
    )

    result = run_workflow_graph(workflow, workflow_context, initial_inputs={"filter": {"Input": input_frame}})

    assert result.node_results["true_select"].outputs["Output"]["account"].tolist() == ["A2", "A3"]
    assert result.node_results["false_select"].outputs["Output"]["amount"].tolist() == [10]
    assert result.execution_order == ["filter", "true_select", "false_select"]


def test_workflow_graph_can_execute_target_ancestors_and_warn_on_frontier(workflow_context):
    input_frame = pd.DataFrame({"account": ["A1", "A2"], "amount": [10, 20]})
    workflow = _workflow(
        nodes=[
            _node("source", "Select", {"select_fields": [{"source": "account"}, {"source": "amount"}]}),
            _node("target", "Formula", {"formula_fields": [{"field": "double_amount", "expression": "[amount] * 2"}]}),
            _node("frontier", "UnsupportedTool", {}),
            _node("unrelated", "UnsupportedTool", {}),
        ],
        edges=[
            _edge("source", "Output", "target"),
            _edge("target", "Output", "frontier"),
        ],
    )

    result = run_workflow_graph(
        workflow,
        workflow_context,
        initial_inputs={"source": {"Input": input_frame}},
        target_node_ids={"target"},
    )

    assert result.execution_order == ["source", "target"]
    assert result.skipped_node_ids == ["frontier", "unrelated"]
    assert result.node_results["target"].outputs["Output"]["double_amount"].tolist() == [20, 40]
    assert workflow_context.warnings == [
        "Skipped frontier node frontier (UnsupportedTool) downstream of target:Output"
    ]


def test_workflow_graph_routes_multiple_edges_to_same_target_anchor(workflow_context):
    workflow = _workflow(
        nodes=[
            _node("left", "Select", {"select_fields": [{"source": "value"}]}),
            _node("right", "Select", {"select_fields": [{"source": "value"}]}),
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
            "left": {"Input": pd.DataFrame({"value": ["A"]})},
            "right": {"Input": pd.DataFrame({"value": ["B"]})},
        },
    )

    assert result.node_results["union"].outputs["Output"]["value"].tolist() == ["A", "B"]


def test_workflow_graph_raises_for_missing_upstream_anchor(workflow_context):
    workflow = _workflow(
        nodes=[
            _node("filter", "Filter", {"expression": "[amount] >= 20"}),
            _node("bad", "Select", {"select_fields": [{"source": "amount"}]}),
        ],
        edges=[_edge("filter", "Missing", "bad")],
    )

    with pytest.raises(KeyError, match="Missing output anchor"):
        run_workflow_graph(
            workflow,
            workflow_context,
            initial_inputs={"filter": {"Input": pd.DataFrame({"amount": [1]})}},
        )
    assert workflow_context.diagnostics[0]["code"] == "missing_upstream_output_anchor"
    assert workflow_context.traces[-1].status == "failed"


def test_workflow_graph_records_schema_drift_diagnostic(workflow_context):
    workflow = _workflow(
        nodes=[
            _node("select", "Select", {"select_fields": [{"source": "customer_id"}]}),
        ],
        edges=[],
    )

    with pytest.raises(KeyError, match="Missing input fields"):
        run_workflow_graph(
            workflow,
            workflow_context,
            initial_inputs={"select": {"Input": pd.DataFrame({"client_id": ["A1"]})}},
        )

    diagnostic = workflow_context.diagnostics[0]
    assert diagnostic["code"] == "missing_input_fields"
    assert diagnostic["node"]["id"] == "select"
    assert diagnostic["missing_fields"] == ["customer_id"]
    assert diagnostic["inputs"]["Input"]["columns"] == ["client_id"]
    assert diagnostic["field_suggestions"]["customer_id"] == ["client_id"]
    assert workflow_context.traces[-1].status == "failed"


def test_workflow_graph_records_missing_input_file_diagnostic(workflow_context, tmp_path):
    missing_path = tmp_path / "missing.csv"
    workflow = _workflow(
        nodes=[
            _node(
                "input",
                "DbFileInput",
                {
                    "file": str(missing_path),
                    "file_attributes": {"FileFormat": "0"},
                },
            ),
        ],
        edges=[],
    )

    with pytest.raises(FileNotFoundError):
        run_workflow_graph(workflow, workflow_context)

    diagnostic = workflow_context.diagnostics[0]
    assert diagnostic["code"] == "missing_input_file"
    assert diagnostic["node"]["id"] == "input"
    assert diagnostic["node"]["tool_type"] == "DbFileInput"
    assert diagnostic["node"]["config_summary"]["file"] == str(missing_path)
    assert "input path is missing" in diagnostic["likely_cause"]
    assert workflow_context.traces[-1].status == "failed"


def test_workflow_graph_stops_on_unsupported_tool(workflow_context):
    workflow = _workflow(
        nodes=[
            NodeIR(
                node_id="1",
                source_tool_id="1",
                tool_type="UnsupportedTool",
                tool_name="CustomMacro.yxmc",
                config={"normalized": {}},
                metadata={"plugin_name": "CustomMacro.yxmc"},
            )
        ],
        edges=[],
    )

    with pytest.raises(NotImplementedError, match="Unsupported workflow tool"):
        run_workflow_graph(workflow, workflow_context)
    assert workflow_context.errors == ["Unsupported workflow tool: UnsupportedTool (node 1)"]
    assert workflow_context.diagnostics[0]["code"] == "unsupported_tool"
    assert workflow_context.diagnostics[0]["node"]["macro_context"]["macro_name"] == "CustomMacro.yxmc"


def test_workflow_graph_rejects_cycles(workflow_context):
    workflow = _workflow(
        nodes=[_node("1", "Select", {"select_fields": [{"source": "x"}]}), _node("2", "Select", {"select_fields": [{"source": "x"}]})],
        edges=[_edge("1", "Output", "2"), _edge("2", "Output", "1")],
    )

    with pytest.raises(ValueError, match="cycle"):
        run_workflow_graph(workflow, workflow_context)
