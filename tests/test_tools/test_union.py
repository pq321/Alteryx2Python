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
