import pandas as pd

from alteryx2python.tools.datacleansing import DataCleansingTool, datacleansing_tool


def test_datacleansing_applies_selected_cleanse_options(workflow_context):
    frame = pd.DataFrame(
        {
            "name": ["  alice  ", "Bob\tSmith", "", None],
            "code": ["A-1", "B  2", "", None],
            "keep": [" x ", " y ", "", None],
        }
    )

    result = datacleansing_tool(
        inputs={"Input2": frame},
        config={
            "node_id": "cleanse",
            "selected_fields": ["name", "code"],
            "remove_null_rows": True,
            "replace_string_nulls": True,
            "remove_leading_trailing_whitespace": True,
            "remove_tabs_line_breaks_duplicate_whitespace": True,
            "modify_case": True,
            "case_mode": "upper",
        },
        context=workflow_context,
    )

    output = result["Output26"]
    assert output.to_dict("records") == [
        {"name": "ALICE", "code": "A-1", "keep": " x "},
        {"name": "BOB SMITH", "code": "B 2", "keep": " y "},
        {"name": "", "code": "", "keep": ""},
    ]
    assert workflow_context.traces[0].tool_type == "DataCleansing"


def test_datacleansing_tool_class_executes_same_contract(workflow_context):
    tool = DataCleansingTool()

    result = tool.execute(
        inputs={"Input2": pd.DataFrame({"value": ["  ok  "]})},
        config={
            "node_id": "cleanse-class",
            "selected_fields": ["value"],
            "remove_leading_trailing_whitespace": True,
        },
        context=workflow_context,
    )

    assert result["Output26"]["value"].tolist() == ["ok"]


def test_datacleansing_uses_type_specific_null_replacements(workflow_context):
    frame = pd.DataFrame({"text": [" x ", None], "number": pd.Series([4, None], dtype="Int64")})
    output = datacleansing_tool(
        {"Input": frame},
        {"replace_string_nulls": True, "replace_numeric_nulls": True,
         "remove_leading_trailing_whitespace": True},
        workflow_context,
    )["Output26"]
    assert output.to_dict("records") == [{"text": "x", "number": 4}, {"text": "", "number": 0}]
    assert output["number"].dtype == frame["number"].dtype


def test_datacleansing_removes_only_all_null_rows_and_columns_across_the_frame(workflow_context):
    frame = pd.DataFrame(
        {"label": [None, None, "", "  foo  "], "keep": ["kept", None, None, None],
         "null": [None] * 4, "empty": [None, None, "", None]},
    )
    output = datacleansing_tool(
        {"Input2": frame},
        {"selected_fields": ["label"], "remove_null_rows": True, "remove_null_columns": True,
         "remove_leading_trailing_whitespace": True},
        workflow_context,
    )["Output26"]
    assert output.astype(object).where(output.notna(), None).to_dict("records") == [
        {"label": None, "keep": "kept", "empty": None},
        {"label": "", "keep": None, "empty": ""},
        {"label": "foo", "keep": None, "empty": None},
    ]


def test_datacleansing_none_or_missing_explicit_fields_are_not_cleaned(workflow_context):
    frame = pd.DataFrame({"label": ["  text  "]})
    for fields in ([], ["removed_from_upstream"]):
        result = datacleansing_tool(
            {"Input2": frame}, {"selected_fields": fields, "remove_leading_trailing_whitespace": True},
            workflow_context,
        )
        pd.testing.assert_frame_equal(result["Output26"], frame)


def test_datacleansing_classic_punctuation_and_title_case(workflow_context):
    frame = pd.DataFrame({"label": ["ABC dON'T O'neil word-WORD", "12hELLo O’NEIL \u3000Ｂ９!?。$∑"]})
    inputs = {"Input2": frame}
    without_punctuation = datacleansing_tool(inputs, {"remove_punctuation": True}, workflow_context)["Output26"]
    title = datacleansing_tool(inputs, {"modify_case": True, "case_mode": "title"}, workflow_context)["Output26"]
    assert without_punctuation["label"].tolist() == ["ABC dONT Oneil wordWORD", "12hELLo ONEIL \u3000Ｂ９"]
    assert title["label"].tolist() == ["Abc Don't O'neil Word-word", "12hello O’Neil \u3000Ｂ９!?。$∑"]
