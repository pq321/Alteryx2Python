import pandas as pd

from alteryx2python.tools.dynamicrename import dynamicrename_tool


def test_dynamicrename_applies_current_field_formula(workflow_context):
    frame = pd.DataFrame({"result_exceptions_0_assetClass": ["EQ"], "RecordID": [1]})

    result = dynamicrename_tool(
        {"Targets": frame},
        {
            "rename_mode": "Formula",
            "expression": 'Replace([_CurrentField_], "result_exceptions_0_", "")',
        },
        workflow_context,
    )

    assert result["Output"].to_dict("records") == [{"assetClass": "EQ", "RecordID": 1}]
