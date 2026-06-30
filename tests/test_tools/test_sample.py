import pandas as pd

from alteryx2python.tools.sample import sample_tool


def test_sample_first_rows(workflow_context):
    frame = pd.DataFrame({"value": [1, 2, 3, 4]})

    output = sample_tool({"Input": frame}, {"mode": "First", "n": 2}, workflow_context)["Output"]

    assert output["value"].tolist() == [1, 2]


def test_sample_first_rows_by_group(workflow_context):
    frame = pd.DataFrame({"city": ["A", "A", "B", "B", "B"], "value": [1, 2, 3, 4, 5]})

    output = sample_tool(
        {"Input": frame},
        {"mode": "First", "n": 2, "group_fields": ["city"]},
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [
        {"city": "A", "value": 1},
        {"city": "A", "value": 2},
        {"city": "B", "value": 3},
        {"city": "B", "value": 4},
    ]
