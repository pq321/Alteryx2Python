import pandas as pd

from alteryx2python.tools.canvas import (
    browsev2_tool,
    controlcontainer_tool,
    textbox_tool,
    toolcontainer_tool,
)


def test_textbox_executes_as_structural_noop(workflow_context):
    result = textbox_tool({}, {"node_id": "note-1"}, workflow_context)

    assert result == {}
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "TextBox"
    assert trace["outputs"] == {}


def test_toolcontainer_executes_as_structural_noop(workflow_context):
    result = toolcontainer_tool({}, {"node_id": "container-1"}, workflow_context)

    assert result == {}
    assert workflow_context.traces[-1].tool_type == "ToolContainer"


def test_controlcontainer_executes_as_structural_noop(workflow_context):
    result = controlcontainer_tool({}, {"node_id": "control-container-1"}, workflow_context)

    assert result == {}
    assert workflow_context.traces[-1].tool_type == "ControlContainer"


def test_browsev2_records_input_as_terminal_sink(workflow_context):
    frame = pd.DataFrame({"a": [1, 2]})

    result = browsev2_tool({"Input": frame}, {"node_id": "browse-1"}, workflow_context)

    assert result == {}
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "BrowseV2"
    assert trace["inputs"]["Input"]["row_count"] == 2
    assert trace["outputs"] == {}
