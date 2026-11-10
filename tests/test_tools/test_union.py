import pandas as pd

from alteryx2python.tools.union import union_tool


def test_union_by_name_all_outputs_combined_rows(workflow_context):
    first = pd.DataFrame({"RecordID": [1], "Value": ["EQ"]})
    second = pd.DataFrame({"Value": ["BUYER-1"], "TargetField": ["Buyer_ID"]})

    result = union_tool(
        {"Input": first, "Input_2": second},
        {"mode": "ByName", "by_name_output_mode": "All"},
        workflow_context,
    )

    assert list(result["Output"].columns) == ["RecordID", "Value", "TargetField"]
    assert result["Output"].to_dict("records") == [
        {"RecordID": 1.0, "Value": "EQ", "TargetField": None},
        {"RecordID": None, "Value": "BUYER-1", "TargetField": "Buyer_ID"},
    ]


def test_union_by_pos_uses_expected_output_schema(workflow_context):
    first = pd.DataFrame({"Field1": ["a"]})
    second = pd.DataFrame({"Concat_Field1": ["b"]})

    result = union_tool(
        {"Input": first, "Input_2": second},
        {
            "mode": "ByPos",
            "expected_output_schema": {"fields": [{"name": "Concat_Field1"}]},
        },
        workflow_context,
    )

    assert list(result["Output"].columns) == ["Concat_Field1"]
    assert result["Output"]["Concat_Field1"].tolist() == ["a", "b"]


def test_union_honors_configured_output_order(workflow_context):
    first = pd.DataFrame({"Field1": ["body"]})
    second = pd.DataFrame({"Field1": ["header"]})

    result = union_tool(
        {"Input": first, "Input_2": second},
        {
            "mode": "ByPos",
            "output_order": ["#1", "#2"],
            "input_connection_names": {"Input": "#2", "Input_2": "#1"},
        },
        workflow_context,
    )

    assert result["Output"]["Field1"].tolist() == ["header", "body"]
