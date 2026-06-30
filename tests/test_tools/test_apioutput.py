import pandas as pd

from alteryx2python.tools.apioutput import APIOutputTool, apioutput_tool


def test_apioutput_records_sink_without_external_write(workflow_context):
    result = apioutput_tool({"Input": pd.DataFrame({"a": [1]})}, {}, workflow_context)

    assert result == {}
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "APIOutput"
    assert trace["config"]["external_api_write_performed"] is False


def test_apioutput_tool_class_executes_same_contract(workflow_context):
    result = APIOutputTool().execute({}, {}, workflow_context)

    assert result == {}
