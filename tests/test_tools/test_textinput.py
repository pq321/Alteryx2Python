import pandas as pd
import pytest

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.macroinput import macroinput_tool
from alteryx2python.tools.textinput import textinput_tool


def test_textinput_tool_infers_native_column_types():
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
    # Native TextInput infers dtypes from the data: CustomerID all-int -> Int64,
    # LastName has an empty cell but is non-numeric -> strings, Score mixes
    # "2" and "a" -> stays string (matching the official Text_Input sample).
    expected = pd.DataFrame(
        {
            "CustomerID": pd.Series([49, 456], dtype="int64"),
            "LastName": pd.Series(["Edison", ""], dtype=object),
            "Score": pd.Series(["2", "a"], dtype=object),
        }
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


def test_textinput_preserves_null_separately_from_explicit_empty_string():
    result = textinput_tool({}, {"fields": ["x"], "rows": [[None], [""]]}, WorkflowContext())
    assert result["Output"].iloc[0, 0] is None
    assert result["Output"].iloc[1, 0] == ""


def test_textinput_numeric_column_maps_empty_cell_to_null():
    result = textinput_tool({}, {"fields": ["x"], "rows": [["1"], [""], ["3"]]}, WorkflowContext())
    values = list(result["Output"]["x"])
    assert values[0] == 1
    assert pd.isna(values[1])
    assert values[2] == 3


def test_textinput_tool_ignores_action_control_anchor():
    result = textinput_tool(
        {"Action": pd.DataFrame({"active": [True]})},
        {"fields": ["x"], "rows": [["1"]]},
        WorkflowContext(),
    )

    assert result["Output"].to_dict("records") == [{"x": 1}]


def test_textinput_tool_rejects_row_width_mismatch():
    with pytest.raises(ValueError, match="row has 1 cells for 2 fields"):
        textinput_tool(
            {},
            {"fields": ["a", "b"], "rows": [["1"]]},
            WorkflowContext(),
        )


def test_macroinput_tool_uses_embedded_textinput_rows():
    context = WorkflowContext()

    result = macroinput_tool(
        {},
        {
            "node_id": "40",
            "source_tool_id": "40",
            "source": "embedded_textinput",
            "fields": ["Account ID", "TD"],
            "rows": [["2081220001", "2024-10-10"]],
            "num_rows": 1,
        },
        context,
    )

    # Native TextInput infers an all-digit column as Int64.
    expected = pd.DataFrame({"Account ID": pd.Series([2081220001], dtype="int64"), "TD": pd.Series(["2024-10-10"], dtype=object)})
    pd.testing.assert_frame_equal(result["Output"], expected)
    assert context.traces[-1].tool_type == "MacroInput"
