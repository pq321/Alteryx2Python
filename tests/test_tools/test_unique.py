import pandas as pd

from alteryx2python.tools.unique import unique_tool


def test_unique_splits_first_rows_and_duplicates(workflow_context):
    frame = pd.DataFrame(
        {
            "FirstName": ["Ada", "Ada", "Grace", "Ada"],
            "LastName": ["Lovelace", "Lovelace", "Hopper", "Byron"],
        }
    )

    outputs = unique_tool(
        {"Input": frame},
        {"unique_fields": ["FirstName", "LastName"]},
        workflow_context,
    )

    assert outputs["Unique"].to_dict("records") == [
        {"FirstName": "Ada", "LastName": "Lovelace"},
        {"FirstName": "Grace", "LastName": "Hopper"},
        {"FirstName": "Ada", "LastName": "Byron"},
    ]
    assert outputs["Duplicates"].to_dict("records") == [
        {"FirstName": "Ada", "LastName": "Lovelace"}
    ]
