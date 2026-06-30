import pandas as pd

from alteryx2python.tools.datacleansepro import datacleansepro_tool


def test_datacleansepro_cleans_selected_text_field(workflow_context):
    frame = pd.DataFrame({"id": [1], "Gender": [" female!!! "], "Other": [" Keep! "]})

    result = datacleansepro_tool(
        {"Input": frame},
        {
            "selected_fields": ["Gender"],
            "remove_leading_trailing_whitespace": True,
            "remove_punctuation": True,
            "modify_case": True,
            "case_mode": "title",
            "replace_string_nulls": True,
            "replace_numeric_nulls": False,
        },
        workflow_context,
    )

    output = result["Output"]
    assert output.to_dict("records") == [{"id": 1, "Gender": "Female", "Other": " Keep! "}]
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "DataCleansePro"
    assert trace["outputs"]["Output"]["columns"] == ["id", "Gender", "Other"]


def test_datacleansepro_can_replace_numeric_nulls(workflow_context):
    frame = pd.DataFrame({"Score": [None, 3]})

    result = datacleansepro_tool(
        {"Input": frame},
        {
            "selected_fields": ["Score"],
            "replace_numeric_nulls": True,
        },
        workflow_context,
    )

    assert result["Output"]["Score"].tolist() == [0, 3]
