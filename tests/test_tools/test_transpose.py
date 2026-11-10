import pandas as pd

from alteryx2python.tools.transpose import transpose_tool


def test_transpose_keeps_keys_and_selected_data_fields(workflow_context):
    frame = pd.DataFrame({"RecordID": [1], "assetClass": ["EQ"], "buyerId": ["BUYER-1"], "ignored": ["x"]})

    result = transpose_tool(
        {"Input": frame},
        {
            "key_fields": ["RecordID"],
            "data_fields": [
                {"field": "assetClass", "selected": True},
                {"field": "buyerId", "selected": True},
                {"field": "ignored", "selected": False},
            ],
        },
        workflow_context,
    )

    assert result["Output"].to_dict("records") == [
        {"RecordID": 1, "Name": "assetClass", "Value": "EQ"},
        {"RecordID": 1, "Name": "buyerId", "Value": "BUYER-1"},
    ]


def test_transpose_orders_selected_fields_by_input_columns(workflow_context):
    frame = pd.DataFrame({"id": ["a"], "b": [2], "a": [1]})

    result = transpose_tool(
        {"Input": frame},
        {
            "key_fields": [],
            "data_fields": [
                {"field": "a", "selected": True},
                {"field": "b", "selected": True},
            ],
        },
        workflow_context,
    )

    assert result["Output"]["Name"].tolist() == ["b", "a"]
