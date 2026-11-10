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


def test_join_overlapping_columns_preserves_multiplicity_and_positional_unmatched_rows(workflow_context):
    left = pd.DataFrame({"key": [2, 1, 1], "label": ["c", "a", "b"]}, index=[10, 10, 20])
    right = pd.DataFrame({"key": [1, 1, 3], "label": ["x", "y", "z"]}, index=[7, 7, 8])
    result = join_tool({"Left": left, "Right": right}, {"joins": [
        {"connection": "Left", "field": "key"}, {"connection": "Right", "field": "key"}]}, workflow_context)
    assert list(result["Join"].columns) == ["Left_key", "Left_label", "Right_key", "Right_label"]
    assert result["Join"][["Left_label", "Right_label"]].values.tolist() == [["a", "x"], ["a", "y"], ["b", "x"], ["b", "y"]]
    assert result["Left"].to_dict("records") == [{"key": 2, "label": "c"}]
    assert result["Right"].to_dict("records") == [{"key": 3, "label": "z"}]
