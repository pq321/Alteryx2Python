import pandas as pd
import pytest

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.sort import sort_tool


def test_sort_tool_sorts_by_configured_fields_stably():
    frame = pd.DataFrame({"CustomerID": [5, 2, 5], "Name": ["b", "a", "c"]})

    result = sort_tool(
        {"Input": frame},
        {"sort_fields": [{"field": "CustomerID", "order": "Ascending"}]},
        WorkflowContext(),
    )

    assert result["Output"].to_dict("records") == [
        {"CustomerID": 2, "Name": "a"},
        {"CustomerID": 5, "Name": "b"},
        {"CustomerID": 5, "Name": "c"},
    ]


def test_sort_tool_supports_descending_order():
    frame = pd.DataFrame({"CustomerID": [5, 2]})

    result = sort_tool(
        {"Input": frame},
        {"sort_fields": [{"field": "CustomerID", "order": "Descending"}]},
        WorkflowContext(),
    )

    assert result["Output"]["CustomerID"].tolist() == [5, 2]


def test_sort_tool_rejects_unknown_order():
    with pytest.raises(ValueError, match="Unsupported Sort order"):
        sort_tool(
            {"Input": pd.DataFrame({"CustomerID": [1]})},
            {"sort_fields": [{"field": "CustomerID", "order": "Sideways"}]},
            WorkflowContext(),
        )
