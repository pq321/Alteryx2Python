import pandas as pd

from alteryx2python.tools.joinmultiple import joinmultiple_tool


def test_joinmultiple_joins_by_fields(workflow_context):
    output = joinmultiple_tool(
        {
            "Input": pd.DataFrame({"Name": ["Ada", "Grace"], "A": [1, 2]}),
            "Input_2": pd.DataFrame({"Name": ["Ada"], "B": [3]}),
            "Input_3": pd.DataFrame({"Name": ["Ada"], "C": [4]}),
        },
        {
            "joins": [
                {"connection": "#1", "fields": ["Name"]},
                {"connection": "#2", "fields": ["Name"]},
                {"connection": "#3", "fields": ["Name"]},
            ]
        },
        workflow_context,
    )["Output"]

    assert len(output.index) == 1
    assert output.loc[0, "Input_#1_Name"] == "Ada"
    assert output.loc[0, "Input_#3_C"] == 4


def test_joinmultiple_joins_by_record_position(workflow_context):
    output = joinmultiple_tool(
        {
            "Input": pd.DataFrame({"Name": ["Ada"]}),
            "Input_2": pd.DataFrame({"Score": [3]}),
        },
        {"join_by_record_position": True},
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [{"Input_#1_Name": "Ada", "Input_#2_Score": 3}]
