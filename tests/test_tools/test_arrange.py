import pandas as pd
import pytest

from alteryx2python.tools.arrange import ArrangeTool, arrange_tool


def test_arrange_expands_configured_columns_to_rows(workflow_context):
    frame = pd.DataFrame({"RecordID": [1], "X1": [10], "X2": [20]})

    output = arrange_tool(
        {"Input": frame},
        {
            "key_fields": ["RecordID"],
            "output_columns": [
                {"name": "Description", "type": "text"},
                {"name": "X", "type": "combobox"},
            ],
            "output_rows": [["Start", "X1"], ["End", "X2"]],
        },
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [
        {"RecordID": 1, "Description": "Start", "X": 10},
        {"RecordID": 1, "Description": "End", "X": 20},
    ]


def test_arrange_rejects_missing_source_field(workflow_context):
    with pytest.raises(KeyError):
        arrange_tool(
            {"Input": pd.DataFrame({"RecordID": [1]})},
            {
                "key_fields": ["RecordID"],
                "output_columns": [{"name": "X", "type": "combobox"}],
                "output_rows": [["Missing"]],
            },
            workflow_context,
        )


def test_arrange_tool_class_executes_same_contract(workflow_context):
    result = ArrangeTool().execute(
        {"Input": pd.DataFrame({"X1": [1]})},
        {"output_columns": [{"name": "X", "type": "combobox"}], "output_rows": [["X1"]]},
        workflow_context,
    )

    assert result["Output"]["X"].tolist() == [1]
