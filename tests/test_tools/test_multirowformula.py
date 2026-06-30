import pandas as pd

from alteryx2python.tools.multirowformula import multirowformula_tool


def test_multirowformula_updates_nulls_from_previous_row(workflow_context):
    frame = pd.DataFrame({"Year": [2024, None, None, 2025]})

    result = multirowformula_tool(
        {"Input": frame},
        {
            "update_field": True,
            "update_field_name": "Year",
            "create_field_type": "Int32",
            "other_rows": "Empty",
            "num_rows": 1,
            "expression": "IF IsNull([Year]) THEN [Row-1:Year] ELSE [Year] ENDIF",
        },
        workflow_context,
    )

    assert result["Output"]["Year"].tolist() == [2024, 2024, 2024, 2025]


def test_multirowformula_creates_grouped_record_ids(workflow_context):
    frame = pd.DataFrame({"Product": ["A", "A", "B", "B"]})

    result = multirowformula_tool(
        {"Input": frame},
        {
            "update_field": False,
            "create_field_name": "RecordID",
            "create_field_type": "Int32",
            "other_rows": "Empty",
            "num_rows": 1,
            "expression": "[Row-1:RecordID]+1",
            "group_by_fields": ["Product"],
        },
        workflow_context,
    )

    assert result["Output"]["RecordID"].tolist() == [1, 2, 1, 2]
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "MultiRowFormula"


def test_multirowformula_supports_nearest_rows_for_moving_average(workflow_context):
    frame = pd.DataFrame({"Product": ["A", "A", "A"], "Sales": [10, 20, 30]})

    result = multirowformula_tool(
        {"Input": frame},
        {
            "update_field": False,
            "create_field_name": "3 Month Average",
            "create_field_type": "FixedDecimal",
            "other_rows": "Nearest",
            "num_rows": 2,
            "expression": "Average([Sales],[Row-1:Sales],[Row-2:Sales])",
            "group_by_fields": ["Product"],
        },
        workflow_context,
    )

    assert result["Output"]["3 Month Average"].tolist() == [10.0, 40.0 / 3.0, 20.0]
