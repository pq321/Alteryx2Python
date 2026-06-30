import pandas as pd

from alteryx2python.tools.dynamicselect import dynamicselect_tool


def test_dynamicselect_selects_string_field_types(workflow_context):
    frame = pd.DataFrame(
        {
            "Name": pd.Series(["A"], dtype="string"),
            "Count": pd.Series([1], dtype="Int64"),
            "Amount": [2.5],
        }
    )

    result = dynamicselect_tool(
        {"Input": frame},
        {"mode": "FieldTypes", "field_types": ["String", "V_String"]},
        workflow_context,
    )

    assert list(result["Output"].columns) == ["Name"]


def test_dynamicselect_selects_by_formula_field_number(workflow_context):
    frame = pd.DataFrame({"first": [1], "second": [2], "third": [3]})

    result = dynamicselect_tool(
        {"Input": frame},
        {"mode": "Formula", "expression": "([FieldNumber] = 1) OR ([FieldNumber] = 3)"},
        workflow_context,
    )

    assert list(result["Output"].columns) == ["first", "third"]
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "DynamicSelect"


def test_dynamicselect_selects_by_formula_name_helpers(workflow_context):
    frame = pd.DataFrame({"datum_price": [1], "datum_type": ["x"], "other": [2]})

    result = dynamicselect_tool(
        {"Input": frame},
        {"mode": "Formula", "expression": "LEFT([Name],6)=='datum_' && RIGHT([Name],4) != 'type'"},
        workflow_context,
    )

    assert list(result["Output"].columns) == ["datum_price"]
