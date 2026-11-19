from decimal import Decimal

import pandas as pd
import pytest

from alteryx2python.parser.tool_parsers.union_parser import parse_union_config
from alteryx2python.tools.union import union_tool


def test_union_by_name_all_outputs_combined_rows(workflow_context):
    first = pd.DataFrame({"RecordID": [1], "Value": ["EQ"]})
    second = pd.DataFrame({"Value": ["BUYER-1"], "TargetField": ["Buyer_ID"]})

    result = union_tool(
        {"Input": first, "Input_2": second},
        {"mode": "ByName", "by_name_output_mode": "All"},
        workflow_context,
    )

    assert list(result["Output"].columns) == ["RecordID", "Value", "TargetField"]
    assert result["Output"].to_dict("records") == [
        {"RecordID": 1.0, "Value": "EQ", "TargetField": None},
        {"RecordID": None, "Value": "BUYER-1", "TargetField": "Buyer_ID"},
    ]


def test_union_by_pos_uses_expected_output_schema(workflow_context):
    first = pd.DataFrame({"Field1": ["a"]})
    second = pd.DataFrame({"Concat_Field1": ["b"]})

    result = union_tool(
        {"Input": first, "Input_2": second},
        {
            "mode": "ByPos",
            "expected_output_schema": {"fields": [{"name": "Concat_Field1"}]},
        },
        workflow_context,
    )

    assert list(result["Output"].columns) == ["Concat_Field1"]
    assert result["Output"]["Concat_Field1"].tolist() == ["a", "b"]


def test_union_honors_configured_output_order(workflow_context):
    first = pd.DataFrame({"Field1": ["body"]})
    second = pd.DataFrame({"Field1": ["header"]})

    result = union_tool(
        {"Input": first, "Input_2": second},
        {
            "mode": "ByPos",
            "output_order": ["#1", "#2"],
            "input_connection_names": {"Input": "#2", "Input_2": "#1"},
        },
        workflow_context,
    )

    assert result["Output"]["Field1"].tolist() == ["header", "body"]


@pytest.mark.parametrize("mode", ["Manual", "ManualDelayed"])
def test_union_manual_reads_saved_connection_mapping(mode, workflow_context):
    config = parse_union_config({
        "Mode": mode,
        "MultiMetaInfo": {"MetaInfo": [
            {"attributes": {"name": "#1"}, "RecordInfo": {"Field": [
                {"attributes": {"name": "Name", "column": "1"}},
                {"attributes": {"name": "Quantity", "column": "2"}},
            ]}},
            {"attributes": {"name": "#2"}, "RecordInfo": {"Field": [
                {"attributes": {"name": "Count", "column": "2"}},
            ]}},
        ]},
    }).normalized_config
    config["input_connection_names"] = {"Input": "#1", "Input_2": "#2"}

    result = union_tool(
        {"Input": pd.DataFrame({"Name": ["one"], "Quantity": [5]}),
         "Input_2": pd.DataFrame({"Count": [7]})},
        config,
        workflow_context,
    )["Output"]

    assert result.to_dict("records") == [
        {"Name": "one", "Quantity": 5},
        {"Name": None, "Quantity": 7},
    ]
    assert isinstance(result.at[1, "Quantity"], int)

@pytest.mark.parametrize("mode", ["ByName", "ByPos", "Manual"])
def test_union_promotes_mixed_keys_to_text_before_stacking(mode, workflow_context):
    right_name = "code" if mode == "ByName" else "lookup"
    left = pd.DataFrame({"code": pd.Series([123, 9007199254740993, None], dtype="Int64")})
    right = pd.DataFrame({right_name: ["00123", "", "ABC"]})
    config = {"mode": mode}
    if mode == "Manual":
        config["manual_inputs"] = {
            "#1": [{"column": 1, "name": "code"}],
            "#2": [{"column": 1, "name": right_name}],
        }

    output = union_tool({"Input": left, "Input_2": right}, config, workflow_context)["Output"]

    assert output["code"].tolist() == ["123", "9007199254740993", None, "00123", "", "ABC"]
    assert left["code"].iloc[0] == 123


def test_union_uses_text_declaration_on_empty_input(workflow_context):
    numbers = pd.DataFrame({"code": [123], "quantity": [10]})
    text = pd.DataFrame({"code": pd.Series(dtype=object), "quantity": pd.Series(dtype="int64")})
    text.attrs["alteryx_schema"] = [{"name": "code", "type": "V_WString", "size": 30}]

    output = union_tool({"Input": numbers, "Input_2": text}, {"mode": "ByName"}, workflow_context)["Output"]

    assert output.to_dict("records") == [{"code": "123", "quantity": 10}]
    assert output.attrs["alteryx_schema"] == [{"name": "code", "type": "V_WString", "size": 30}]

def test_union_formats_values_using_designer_text_widths(workflow_context):
    numeric = pd.DataFrame({
        "integer": pd.Series([-2147483648], dtype="Int32"),
        "fraction": pd.Series([1.23456789], dtype="float32"),
        "exponent": [1e20],
        "decimal": [Decimal("123.2500")],
        "flag": [False],
    })
    declarations = [("integer", "Int32", 4), ("fraction", "Float", 4), ("exponent", "Double", 8),
                    ("decimal", "FixedDecimal", "16.4"), ("flag", "Bool", 1)]
    numeric.attrs["alteryx_schema"] = [
        {"name": name, "type": kind, "size": size} for name, kind, size in declarations
    ]
    text = pd.DataFrame({column: ["X"] for column in numeric})
    text.attrs["alteryx_schema"] = [{"name": column, "type": "String", "size": 1} for column in text]

    output = union_tool({"Input": numeric, "Input_2": text}, {"mode": "ByName"}, workflow_context)["Output"]

    assert output.iloc[0].tolist() == ["-214748364", "1.234568", "1.e+20", "123.2500", "False"]
    assert [(field["type"], field["size"]) for field in output.attrs["alteryx_schema"]] == [
        ("V_String", 10), ("V_String", 13), ("V_String", 23), ("V_String", 16), ("V_String", 5),
    ]
