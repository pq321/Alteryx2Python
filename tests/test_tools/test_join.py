import pandas as pd

from alteryx2python.tools.join import join_tool


def test_join_matches_left_and_right_keys_and_selects_join_output(workflow_context):
    left = pd.DataFrame({"RecordID": [1, 2], "Name": ["assetClass", "missing"], "Value": ["EQ", "x"]})
    right = pd.DataFrame(
        {
            "SourceField": ["assetClass"],
            "OutputOrder": [1],
            "TargetField": ["Report_Status"],
        }
    )

    result = join_tool(
        {"Left": left, "Right": right},
        {
            "joins": [
                {"connection": "Left", "field": "Name"},
                {"connection": "Right", "field": "SourceField"},
            ],
            "select_fields": [
                {"source": "Left_RecordID", "rename": "RecordID", "selected": True},
                {"source": "Left_Value", "rename": "Value", "selected": True},
                {"source": "Right_OutputOrder", "rename": "OutputOrder", "selected": True},
                {"source": "Right_TargetField", "rename": "TargetField", "selected": True},
            ],
        },
        workflow_context,
    )

    assert result["Join"].to_dict("records") == [
        {"RecordID": 1, "Value": "EQ", "OutputOrder": 1, "TargetField": "Report_Status"}
    ]
    assert result["Left"].to_dict("records") == [{"RecordID": 2, "Name": "missing", "Value": "x"}]
    assert result["Right"].empty
