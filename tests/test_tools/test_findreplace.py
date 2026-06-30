import pandas as pd

from alteryx2python.tools.findreplace import findreplace_tool


def test_findreplace_replaces_multiple_matches(workflow_context):
    targets = pd.DataFrame({"acct_holder": ["GLEN & ALLENS CO", "WOLFMAN CMPY"]})
    source = pd.DataFrame({"word": ["&", "CO", "CMPY"], "replacement": ["AND", "COMPANY", "COMPANY"]})

    output = findreplace_tool(
        {"Targets": targets, "Source": source},
        {
            "field_find": "acct_holder",
            "field_search": "word",
            "replace_found_field": "replacement",
            "find_mode": "FindAny",
            "replace_mode": "Replace",
            "replace_multiple_found": True,
        },
        workflow_context,
    )["Output"]

    assert output["acct_holder"].tolist() == ["GLEN AND ALLENS COMPANY", "WOLFMAN COMPANY"]


def test_findreplace_appends_lookup_fields_case_insensitive(workflow_context):
    targets = pd.DataFrame({"acct_holder": ["Colorado Department of Revenue", "WOLFMAN CO"]})
    source = pd.DataFrame({"gov_string": ["revenue", "treasury"], "gov_flag": ["Y", "Y"]})

    output = findreplace_tool(
        {"Targets": targets, "Source": source},
        {
            "field_find": "acct_holder",
            "field_search": "gov_string",
            "find_mode": "FindAny",
            "no_case": True,
            "replace_mode": "Append",
            "append_fields": ["gov_flag"],
        },
        workflow_context,
    )["Output"]

    assert output["gov_flag"].tolist() == ["Y", None]
