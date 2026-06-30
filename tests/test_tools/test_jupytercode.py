import pandas as pd

from alteryx2python.tools.jupytercode import JupyterCodeTool, jupytercode_tool


def test_jupytercode_does_not_execute_embedded_script(workflow_context):
    frame = pd.DataFrame({"a": [1]})

    output = jupytercode_tool(
        {"Input": frame},
        {"venv_name": "designerbasetools_venv", "production_mode_script": "raise RuntimeError()"},
        workflow_context,
    )["Output"]

    pd.testing.assert_frame_equal(output, frame)
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "JupyterCode"
    assert trace["config"]["external_code_executed"] is False


def test_jupytercode_tool_class_executes_same_contract(workflow_context):
    result = JupyterCodeTool().execute({}, {}, workflow_context)

    assert result["Output"].empty
