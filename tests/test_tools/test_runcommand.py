import pandas as pd

from alteryx2python.tools.runcommand import RunCommandTool, runcommand_tool


def test_runcommand_records_external_command_without_executing(workflow_context):
    frame = pd.DataFrame({"a": [1]})

    result = runcommand_tool(
        {"Input": frame},
        {"program_name": "script.bat", "arguments": "/q", "output_file": "out.yxdb"},
        workflow_context,
    )

    assert result["Output"].to_dict("records") == [{"a": 1}]
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "RunCommand"
    assert trace["config"]["program_name"] == "script.bat"
    assert trace["config"]["external_command_executed"] is False


def test_runcommand_without_input_emits_empty_output(workflow_context):
    result = RunCommandTool().execute({}, {"program_name": "script.bat"}, workflow_context)

    assert result["Output"].empty
