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
