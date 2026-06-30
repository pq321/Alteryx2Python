import pandas as pd

from alteryx2python.tools.crosstab import crosstab_tool


def test_crosstab_groups_headers_and_takes_first_value(workflow_context):
    frame = pd.DataFrame(
        [
            {"RecordID": 1, "FieldKey": "assetClass", "JSON_ValueString": "EQ"},
            {"RecordID": 1, "FieldKey": "buyerId", "JSON_ValueString": "BUYER-1"},
            {"RecordID": 1, "FieldKey": "assetClass", "JSON_ValueString": "DUP"},
            {"RecordID": 2, "FieldKey": "assetClass", "JSON_ValueString": "FX"},
        ]
    )

    result = crosstab_tool(
        {"Input": frame},
        {
            "group_fields": ["RecordID"],
            "header_field": "FieldKey",
            "data_field": "JSON_ValueString",
            "method": "First",
        },
        workflow_context,
    )

    output = result["Output"]
    assert list(output.columns) == ["RecordID", "assetClass", "buyerId"]
    assert output.to_dict("records") == [
        {"RecordID": 1, "assetClass": "EQ", "buyerId": "BUYER-1"},
        {"RecordID": 2, "assetClass": "FX", "buyerId": None},
    ]
