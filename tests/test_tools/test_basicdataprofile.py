import pandas as pd
import pytest

from alteryx2python.tools.basicdataprofile import BasicDataProfileTool, basicdataprofile_tool


def test_basicdataprofile_emits_field_profile_rows(workflow_context):
    frame = pd.DataFrame({"name": ["a", "a", None], "amount": [1, 2, 2]})

    output = basicdataprofile_tool({"Input": frame}, {}, workflow_context)["Output"]

    assert output[["Field", "Count", "NullCount", "UniqueCount"]].to_dict("records") == [
        {"Field": "name", "Count": 2, "NullCount": 1, "UniqueCount": 1},
        {"Field": "amount", "Count": 3, "NullCount": 0, "UniqueCount": 2},
    ]


def test_basicdataprofile_rejects_missing_input(workflow_context):
    with pytest.raises(KeyError, match="requires an Input anchor"):
        basicdataprofile_tool({}, {}, workflow_context)


def test_basicdataprofile_tool_class_executes_same_contract(workflow_context):
    result = BasicDataProfileTool().execute({"Input": pd.DataFrame({"a": [1]})}, {}, workflow_context)

    assert result["Output"]["Field"].tolist() == ["a"]
