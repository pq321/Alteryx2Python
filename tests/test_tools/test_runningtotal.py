import pandas as pd

from alteryx2python.tools.runningtotal import runningtotal_tool


def test_runningtotal_resets_by_group(workflow_context):
    frame = pd.DataFrame({"City": ["A", "A", "B"], "Spend": [10, 5, 7]})

    output = runningtotal_tool(
        {"Input": frame},
        {"group_by_fields": ["City"], "running_total_fields": ["Spend"]},
        workflow_context,
    )["Output"]

    assert output["RunningTotal_Spend"].tolist() == [10, 15, 7]
