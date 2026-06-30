import pandas as pd

from alteryx2python.tools.datetime import datetime_tool


def test_datetime_formats_iso_date(workflow_context):
    frame = pd.DataFrame({"Join Date": ["2005-01-10"]})

    output = datetime_tool(
        {"Input": frame},
        {
            "is_from": True,
            "input_field_name": "Join Date",
            "format": "Month dd, yyyy",
            "output_field_name": "Join Date_New",
        },
        workflow_context,
    )["Output"]

    assert output["Join Date_New"].tolist() == ["January 10, 2005"]


def test_datetime_parses_formatted_date(workflow_context):
    frame = pd.DataFrame({"DOB": ["January 24, 1977"]})

    output = datetime_tool(
        {"Input": frame},
        {
            "is_from": False,
            "input_field_name": "DOB",
            "format": "Month dd, yyyy",
            "output_field_name": "DOB_New",
        },
        workflow_context,
    )["Output"]

    assert output["DOB_New"].tolist() == ["1977-01-24"]
