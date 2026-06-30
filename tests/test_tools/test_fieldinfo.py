import pandas as pd

from alteryx2python.tools.fieldinfo import fieldinfo_tool


def test_fieldinfo_emits_column_metadata(workflow_context):
    frame = pd.DataFrame({"name": ["Ada"], "amount": [1.5]})

    output = fieldinfo_tool({"Input": frame}, {}, workflow_context)["Output"]

    assert output["Name"].tolist() == ["name", "amount"]
    assert set(["Type", "Size", "Scale", "Source", "Description"]).issubset(output.columns)
