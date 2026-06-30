import pandas as pd

from alteryx2python.tools.makecolumns import makecolumns_tool


def test_makecolumns_groups_rows_into_wide_records(workflow_context):
    output = makecolumns_tool(
        {"Input": pd.DataFrame({"value": [1, 2, 3, 4]})},
        {"num_columns": 3, "is_horizontal": True},
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [
        {"value_1": 1, "value_2": 2, "value_3": 3},
        {"value_1": 4, "value_2": None, "value_3": None},
    ]


def test_makecolumns_respects_groups(workflow_context):
    output = makecolumns_tool(
        {"Input": pd.DataFrame({"Code": ["A", "A", "B"], "value": [1, 2, 3]})},
        {"num_columns": 2, "group_fields": ["Code"]},
        workflow_context,
    )["Output"]

    assert output["value_1"].tolist() == [1, 3]
