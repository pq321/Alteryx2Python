import pandas as pd

from alteryx2python.tools.multifieldformula import multifieldformula_tool


def test_multifieldformula_overwrites_selected_fields(workflow_context):
    frame = pd.DataFrame({"NAME": ["alice"], "CITY": ["new york"], "ID": [1]})

    output = multifieldformula_tool(
        {"Input": frame},
        {"fields": ["NAME", "CITY"], "expression": "Uppercase([_CurrentField_])"},
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [{"NAME": "ALICE", "CITY": "NEW YORK", "ID": 1}]


def test_multifieldformula_copies_outputs_with_suffix(workflow_context):
    frame = pd.DataFrame({"January": [10], "February": [30], "Total ": [40]})

    output = multifieldformula_tool(
        {"Input": frame},
        {
            "fields": ["January", "February"],
            "copy_output": True,
            "new_field_add_on": " % Total",
            "new_field_add_on_pos": "Suffix",
            "expression": "[_CurrentField_]/[Total ]*100",
        },
        workflow_context,
    )["Output"]

    assert output["January % Total"].tolist() == [25.0]
    assert output["February % Total"].tolist() == [75.0]
