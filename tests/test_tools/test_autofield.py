import pandas as pd

from alteryx2python.tools.autofield import autofield_tool


def test_autofield_converts_numeric_strings(workflow_context):
    frame = pd.DataFrame({"id": ["1", "2", ""], "name": ["a", "b", "c"]})

    output = autofield_tool(
        {"Input": frame},
        {"fields": ["id"]},
        workflow_context,
    )["Output"]

    assert str(output["id"].dtype) == "Int64"
    assert output["name"].tolist() == ["a", "b", "c"]
