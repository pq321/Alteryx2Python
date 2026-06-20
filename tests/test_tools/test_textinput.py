import pandas as pd
import pytest

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.textinput import textinput_tool


def test_textinput_tool_builds_embedded_dataframe_with_string_values():
    context = WorkflowContext()

    result = textinput_tool(
        {},
        {
            "node_id": "98",
            "source_tool_id": "98",
            "fields": ["CustomerID", "LastName", "Score"],
            "rows": [["49", "Edison", "2"], ["456", "", "a"]],
            "num_rows": 2,
        },
        context,
    )

    output = result["Output"]
    expected = pd.DataFrame(
        {
            "CustomerID": ["49", "456"],
            "LastName": ["Edison", ""],
            "Score": ["2", "a"],
        },
        dtype=object,
    )
    pd.testing.assert_frame_equal(output, expected)
    assert context.traces[-1].tool_type == "TextInput"
    assert context.traces[-1].outputs["Output"].row_count == 2


def test_textinput_tool_rejects_input_anchors():
    with pytest.raises(ValueError, match="does not accept input anchors"):
        textinput_tool(
            {"Input": pd.DataFrame({"x": [1]})},
            {"fields": ["x"], "rows": [["1"]]},
            WorkflowContext(),
        )


def test_textinput_tool_rejects_row_width_mismatch():
    with pytest.raises(ValueError, match="row has 1 cells for 2 fields"):
        textinput_tool(
            {},
            {"fields": ["a", "b"], "rows": [["1"]]},
            WorkflowContext(),
        )
