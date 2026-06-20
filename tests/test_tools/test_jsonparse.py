import pandas as pd
import pytest

from alteryx2python.tools.jsonparse import jsonparse_tool


def test_jsonparse_single_field_outputs_name_value_pairs(workflow_context):
    frame = pd.DataFrame({"id": [1], "Field1": ['{"name":"Ada","address":{"city":"London"}}']})

    result = jsonparse_tool(
        {"Input": frame},
        {"json_field": "Field1", "include_in_output": False, "single_field": True},
        workflow_context,
    )

    output = result["Output"]
    assert list(output.columns) == ["id", "JSON_Name", "JSON_ValueString"]
    assert output.to_dict("records") == [
        {"id": 1, "JSON_Name": "name", "JSON_ValueString": "Ada"},
        {"id": 1, "JSON_Name": "address.city", "JSON_ValueString": "London"},
    ]
    trace = workflow_context.traces[-1].to_dict()
    assert trace["outputs"]["Output"]["row_count"] == 2
    assert trace["outputs"]["Output"]["columns"] == ["id", "JSON_Name", "JSON_ValueString"]


def test_jsonparse_can_include_original_columns(workflow_context):
    frame = pd.DataFrame({"id": [1], "payload": ['{"active":true}']})

    result = jsonparse_tool(
        {"Input": frame},
        {"json_field": "payload", "include_in_output": True, "single_field": True},
        workflow_context,
    )

    assert result["Output"].to_dict("records") == [
        {"id": 1, "payload": '{"active":true}', "JSON_Name": "active", "JSON_ValueString": "True"}
    ]


def test_jsonparse_rejects_missing_json_field(workflow_context):
    with pytest.raises(KeyError, match="Missing input fields: payload"):
        jsonparse_tool(
            {"Input": pd.DataFrame({"other": ["{}"]})},
            {"json_field": "payload"},
            workflow_context,
        )
