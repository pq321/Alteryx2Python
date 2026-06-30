import pandas as pd

from alteryx2python.tools.texttocolumns import texttocolumns_tool


def test_texttocolumns_splits_to_columns(workflow_context):
    frame = pd.DataFrame({"Address": ["123 Main,New York,NY,10001"]})

    output = texttocolumns_tool(
        {"Input": frame},
        {
            "field": "Address",
            "root_name": "Address",
            "delimiters": ",",
            "num_fields": 3,
            "error_handling": "Last",
            "flags": 0,
        },
        workflow_context,
    )["Output"]

    assert output[["Address1", "Address2", "Address3"]].to_dict("records") == [
        {"Address1": "123 Main", "Address2": "New York", "Address3": "NY,10001"}
    ]


def test_texttocolumns_splits_to_rows(workflow_context):
    frame = pd.DataFrame({"tags": ["a|b c"]})

    output = texttocolumns_tool(
        {"Input": frame},
        {"field": "tags", "delimiters": r"|\s", "flags": 1},
        workflow_context,
    )["Output"]

    assert output["tags"].tolist() == ["a", "b", "c"]
