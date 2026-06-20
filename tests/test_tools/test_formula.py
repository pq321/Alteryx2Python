import pandas as pd
import pytest

from alteryx2python.expressions.errors import UnsupportedExpressionError
from alteryx2python.tools.formula import formula_tool


def test_formula_adds_and_updates_columns_sequentially(workflow_context):
    frame = pd.DataFrame(
        {
            "City": ["new york", "los angeles"],
            "Latitude": [40.7, 34.0],
            "Spend": [20.0, 15.0],
            "Visits": [4, 2],
        }
    )

    result = formula_tool(
        {"Input": frame},
        {
            "node_id": "formula-1",
            "formula_fields": [
                {"field": "RecordSource", "expression": '"Alteryx Sample Data"', "enabled": True},
                {
                    "field": "Region",
                    "expression": 'IF [Latitude] > 39.7 THEN "North" ELSE "South" ENDIF',
                    "enabled": True,
                },
                {"field": "City", "expression": "Titlecase([City])", "enabled": True},
                {"field": "AverageSpendPerVisit", "expression": "ROUND([Spend]/[Visits], 1)", "enabled": True},
            ],
        },
        workflow_context,
    )

    output = result["Output"]
    assert output["RecordSource"].tolist() == ["Alteryx Sample Data", "Alteryx Sample Data"]
    assert output["Region"].tolist() == ["North", "South"]
    assert output["City"].tolist() == ["New York", "Los Angeles"]
    assert output["AverageSpendPerVisit"].tolist() == [5.0, 7.5]
    assert list(output.columns) == ["City", "Latitude", "Spend", "Visits", "RecordSource", "Region", "AverageSpendPerVisit"]
    trace = workflow_context.traces[-1].to_dict()
    assert trace["outputs"]["Output"]["row_count"] == 2
    assert trace["outputs"]["Output"]["columns"] == list(output.columns)


def test_formula_rejects_unsupported_expression(workflow_context):
    with pytest.raises(UnsupportedExpressionError, match="Unsupported expression function"):
        formula_tool(
            {"Input": pd.DataFrame({"x": [1]})},
            {"formula_fields": [{"field": "today", "expression": "DateTimeToday()"}]},
            workflow_context,
        )


def test_formula_rejects_empty_field_list(workflow_context):
    with pytest.raises(ValueError, match="non-empty formula_fields"):
        formula_tool({"Input": pd.DataFrame({"x": [1]})}, {"formula_fields": []}, workflow_context)
