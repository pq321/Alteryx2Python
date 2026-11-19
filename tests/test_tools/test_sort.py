import pandas as pd
import pytest

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools import sort
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


def test_sort_uses_null_precedence_per_field_direction():
    frame = pd.DataFrame({
        "Group": ["A", "A", None, "A", None], "Quantity": [None, 3, 1, 3, 2], "Source": range(5),
    })
    result = sort_tool(
        {"Input": frame},
        {"sort_locale": 0, "sort_fields": [{"field": "Group", "order": "Ascending"},
                                           {"field": "Quantity", "order": "Descending"}]},
        WorkflowContext(),
    )
    assert result["Output"]["Source"].tolist() == [4, 2, 1, 3, 0]


def test_dictionary_sort_numeric_text_needs_no_platform_collation(monkeypatch):
    def unexpected_lookup(locale):
        pytest.fail(f"Numeric sort did not need a collation library for {locale}")

    monkeypatch.setattr(sort, "_windows_collation", unexpected_lookup)
    result = sort.sort_frame(pd.DataFrame({"Value": ["11", None, "05", "5"]}), ["Value"], [True], "en-US")
    assert pd.isna(result["Value"].iloc[0])
    assert result["Value"].iloc[1:].tolist() == ["05", "5", "11"]
