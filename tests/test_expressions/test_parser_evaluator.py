import pytest

from alteryx2python.expressions.errors import UnsupportedExpressionError
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression


def eval_expr(expression, row):
    return evaluate_expression(parse_expression(expression), row)


def test_expression_evaluates_literals_fields_and_arithmetic():
    row = {"Spend": 19.95, "Visits": 4}

    assert eval_expr('"Alteryx Sample Data"', row) == "Alteryx Sample Data"
    assert eval_expr("[Spend]/[Visits]", row) == pytest.approx(4.9875)
    assert eval_expr("ROUND([Spend]/[Visits], 1)", row) == pytest.approx(5.0)


def test_expression_evaluates_if_then_else_and_titlecase():
    assert eval_expr('IF [Latitude] > 39.7 THEN "North" ELSE "South" ENDIF', {"Latitude": 40.1}) == "North"
    assert eval_expr('IF [Latitude] > 39.7 THEN "North" ELSE "South" ENDIF', {"Latitude": 38.5}) == "South"
    assert eval_expr("Titlecase([City])", {"City": "new york"}) == "New York"


def test_expression_evaluates_filter_functions_and_boolean_logic():
    row = {"FieldKey": "result_name", "LastName": None, "Region": "southwest"}

    assert eval_expr('StartsWith([FieldKey], "result_")', row) is True
    assert eval_expr("!IsNull([LastName])", row) is False
    assert eval_expr('[Region]=="South" OR REGEX_Match(UPPERCASE([Region]), ".*WEST")', row) is True
    assert eval_expr('REGEX_Replace([FieldKey], "[^A-Za-z0-9_]", "_")', row) == "result_name"


def test_expression_evaluates_mifid_reshape_functions():
    assert eval_expr('Replace([_CurrentField_], "result_exceptions_0_", "")', {"_CurrentField_": "result_exceptions_0_assetClass"}) == "assetClass"
    assert eval_expr('PadLeft(ToString([OutputOrder]), 3, "0") + "_" + [TargetField]', {"OutputOrder": 7, "TargetField": "Report_Status"}) == "007_Report_Status"
    assert eval_expr('IF IsEmpty([Value]) THEN "" ELSE ToString([Value]) ENDIF', {"Value": None}) == ""
    assert eval_expr('IF IsEmpty([Value]) THEN "" ELSE ToString([Value]) ENDIF', {"Value": 10}) == "10"


def test_expression_rejects_unsupported_functions_explicitly():
    with pytest.raises(UnsupportedExpressionError, match="Unsupported expression function"):
        eval_expr("DateTimeToday()", {})
