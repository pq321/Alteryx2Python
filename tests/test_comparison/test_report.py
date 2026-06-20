import pandas as pd

from alteryx2python.comparison.dataframe_diff import compare_dataframes
from alteryx2python.comparison.report import build_dataframe_comparison_report


def test_compare_dataframes_reports_value_differences():
    left = pd.DataFrame({"a": [1, 2], "b": ["x", None]})
    right = pd.DataFrame({"a": [1, 3], "b": ["x", None]})

    diff = compare_dataframes(left, right)

    assert diff.matches is False
    assert diff.issues == ["Value mismatch count: 1"]
    assert diff.value_differences[0].to_dict() == {
        "row_index": 1,
        "column": "a",
        "left": 2,
        "right": 3,
    }


def test_dataframe_comparison_report_has_machine_and_human_output():
    left = pd.DataFrame({"a": [1], "b": ["x"]})
    right = pd.DataFrame({"a": [1], "b": ["x"]})

    report = build_dataframe_comparison_report("slice-1", left, right)

    assert report.summary() == "slice-1: match (1 rows, 2 columns)"
    assert report.to_dict() == {
        "name": "slice-1",
        "status": "match",
        "left_row_count": 1,
        "right_row_count": 1,
        "columns": ["a", "b"],
        "diff": {"matches": True, "issues": [], "value_differences": []},
    }


def test_dataframe_comparison_report_summarizes_schema_mismatch():
    left = pd.DataFrame({"a": [1]})
    right = pd.DataFrame({"b": [1]})

    report = build_dataframe_comparison_report("slice-1", left, right)

    assert report.status == "mismatch"
    assert report.summary() == "slice-1: mismatch (Column order or names differ; Column dtypes differ)"
