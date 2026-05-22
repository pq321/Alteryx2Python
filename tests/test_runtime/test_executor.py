from alteryx2python.runtime.executor import run_tool_node
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