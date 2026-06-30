import pandas as pd
import pytest

from alteryx2python.tools.appendfields import appendfields_tool


def test_appendfields_allows_cartesian_append(workflow_context):
    targets = pd.DataFrame({"id": [1, 2]})
    source = pd.DataFrame({"label": ["A", "B"]})

    output = appendfields_tool(
        {"Targets": targets, "Source": source},
        {"cartesian_mode": "Allow"},
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [
        {"id": 1, "label": "A"},
        {"id": 1, "label": "B"},
        {"id": 2, "label": "A"},
        {"id": 2, "label": "B"},
    ]


def test_appendfields_error_mode_rejects_many_to_many(workflow_context):
    with pytest.raises(ValueError, match="many-to-many"):
        appendfields_tool(
            {"Targets": pd.DataFrame({"id": [1, 2]}), "Source": pd.DataFrame({"label": ["A", "B"]})},
            {"cartesian_mode": "Error"},
            workflow_context,
        )
