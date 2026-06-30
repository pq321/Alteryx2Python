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
