import pandas as pd
import pytest

from alteryx2python.tools.recordid import recordid_tool


def test_recordid_adds_first_column_starting_at_one(workflow_context):
    frame = pd.DataFrame({"Name": ["A", "B", "C"]})

    result = recordid_tool(
        {"Input": frame},
        {"field_name": "Record ID", "start_value": 1, "field_type": "Int64", "position": 0},
        workflow_context,
    )

    output = result["Output"]
    assert list(output.columns) == ["Record ID", "Name"]
    assert output["Record ID"].tolist() == [1, 2, 3]
    assert str(output["Record ID"].dtype) == "Int64"
    trace = workflow_context.traces[-1].to_dict()
    assert trace["outputs"]["Output"]["row_count"] == 3
    assert trace["outputs"]["Output"]["columns"] == ["Record ID", "Name"]


def test_recordid_can_append_last_column_with_negative_start(workflow_context):
    frame = pd.DataFrame({"Name": ["A", "B"]})

    result = recordid_tool(
        {"Input": frame},
        {"field_name": "Record ID Last Column", "start_value": -100, "field_type": "Int32", "position": 1},
        workflow_context,
    )

    output = result["Output"]
    assert list(output.columns) == ["Name", "Record ID Last Column"]
    assert output["Record ID Last Column"].tolist() == [-100, -99]


def test_recordid_rejects_unsupported_field_type(workflow_context):
    with pytest.raises(ValueError, match="Unsupported RecordID field_type"):
        recordid_tool(
            {"Input": pd.DataFrame({"Name": ["A"]})},
            {"field_name": "Record ID", "field_type": "String"},
            workflow_context,
        )
