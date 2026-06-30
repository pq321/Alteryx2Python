import pandas as pd

from alteryx2python.tools.regex import regex_tool


def test_regex_replace_uses_capture_references(workflow_context):
    frame = pd.DataFrame({"Address": ["Main,New York,NY 10001"]})

    output = regex_tool(
        {"Input": frame},
        {
            "field": "Address",
            "regex_expression": r"(.*),(.*),(.*)\s(\d{5})",
            "method": "Replace",
            "replace_expression": "$4: $2, $3",
            "case_insensitive": True,
        },
        workflow_context,
    )["Output"]

    assert output["Address"].tolist() == ["10001: New York, NY"]


def test_regex_parse_complex_outputs_groups(workflow_context):
    frame = pd.DataFrame({"Name": ["ada lovelace"]})

    output = regex_tool(
        {"Input": frame},
        {
            "field": "Name",
            "regex_expression": r"([a-z]+)\s([a-z]+)",
            "method": "ParseComplex",
            "parse_complex_fields": ["First Name", "Last Name"],
            "case_insensitive": True,
        },
        workflow_context,
    )["Output"]

    assert output[["First Name", "Last Name"]].to_dict("records") == [
        {"First Name": "ada", "Last Name": "lovelace"}
    ]
