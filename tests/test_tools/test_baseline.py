import pandas as pd

from alteryx2python.tools.baseline import BaselineTool, baseline_tool


def test_baseline_uses_node_output_anchors(workflow_context):
    frame = pd.DataFrame({"value": [1]})

    outputs = baseline_tool(
        "Predict",
        {"Data": frame},
        {"node_output_anchors": ["PredictedData"]},
        workflow_context,
    )

    assert list(outputs) == ["PredictedData"]
    pd.testing.assert_frame_equal(outputs["PredictedData"], frame)
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "Predict"
    assert trace["config"]["baseline_semantics"] == "passthrough_or_metadata_only"


def test_baseline_emits_metadata_without_input(workflow_context):
    outputs = baseline_tool("CalgaryInput", {}, {"node_output_anchors": ["Output"]}, workflow_context)

    assert outputs["Output"].loc[0, "tool_type"] == "CalgaryInput"
    assert outputs["Output"].loc[0, "baseline_semantics"] == "metadata_only"


def test_baseline_tool_class_uses_configured_tool_type(workflow_context):
    outputs = BaselineTool().execute(
        {},
        {"tool_type": "UNKNOWN", "node_output_anchors": ["Output13"]},
        workflow_context,
    )

    assert "Output13" in outputs
    assert workflow_context.traces[-1].tool_type == "UNKNOWN"
