import pandas as pd

from alteryx2python.tools.generaterows import generaterows_tool


def test_generaterows_creates_rows_without_input(workflow_context):
    output = generaterows_tool(
        {},
        {
            "create_field_name": "RowCount",
            "expression_init": "1",
            "expression_cond": "RowCount <= 3",
            "expression_loop": "RowCount + 1",
        },
        workflow_context,
    )["Output"]

    assert output["RowCount"].tolist() == [1, 2, 3]


def test_generaterows_uses_input_row_values(workflow_context):
    output = generaterows_tool(
        {"Input": pd.DataFrame({"authorized_users": [2, 3]})},
        {
            "create_field_name": "Authorized_UserNo",
            "expression_init": "1",
            "expression_cond": "Authorized_UserNo <= [authorized_users]",
            "expression_loop": "Authorized_UserNo + 1",
        },
        workflow_context,
    )["Output"]

    assert output["Authorized_UserNo"].tolist() == [1, 2, 1, 2, 3]


def test_generaterows_supports_elseif(workflow_context):
    output = generaterows_tool(
        {"Input": pd.DataFrame({"category": ["A"], "maxValue": [20], "minValue": [0]})},
        {
            "create_field_name": "whatIfTestValue",
            "expression_init": "[maxValue]",
            "expression_cond": "[whatIfTestValue] >= [minValue]",
            "expression_loop": "If [category]='A' Then [whatIfTestValue] - 10 ElseIf [category]='B' Then [whatIfTestValue] - 1 Else [minValue]-1 EndIf",
        },
        workflow_context,
    )["Output"]

    assert output["whatIfTestValue"].tolist() == [20, 10, 0]


def test_generaterows_supports_datetimeadd(workflow_context):
    output = generaterows_tool(
        {"Input": pd.DataFrame({"accountOpenDt": ["2026-06-20"], "accountCloseDt": ["2026-06-22"]})},
        {
            "create_field_name": "date",
            "expression_init": "[accountOpenDt]",
            "expression_cond": "[date] <= [accountCloseDt]",
            "expression_loop": "DateTimeAdd([date],1,\"days\")",
        },
        workflow_context,
    )["Output"]

    assert output["date"].tolist() == ["2026-06-20", "2026-06-21", "2026-06-22"]
