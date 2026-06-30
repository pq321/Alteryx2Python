import pandas as pd

from alteryx2python.tools.dynamicinput import DynamicInputTool, dynamicinput_tool


def test_dynamicinput_passes_input_without_external_read(workflow_context):
    frame = pd.DataFrame({"Latitude": [1.0], "Longitude": [2.0]})

    output = dynamicinput_tool({"Input": frame}, {"mode": "ModifySQL"}, workflow_context)["Output"]

    pd.testing.assert_frame_equal(output, frame)
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "DynamicInput"
    assert trace["config"]["external_input_read_performed"] is False


def test_dynamicinput_tool_class_executes_same_contract(workflow_context):
    result = DynamicInputTool().execute({}, {}, workflow_context)

    assert result["Output"].empty
