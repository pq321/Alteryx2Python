import pandas as pd
import pytest

from alteryx2python.tools.summarize import summarize_tool


def test_summarize_groups_and_aggregates(workflow_context):
    frame = pd.DataFrame({"City": ["A", "A", "B"], "Spend": [10, 5, 7], "Name": ["Ada", "Alan", "Grace"]})

    output = summarize_tool(
        {"Input": frame},
        {
            "summarize_fields": [
                {"field": "City", "action": "GroupBy", "rename": "City"},
                {"field": "Spend", "action": "Sum", "rename": "Sum_Spend"},
                {"field": "Name", "action": "Concat", "rename": "Names", "separator": "|"},
            ]
        },
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [
        {"City": "A", "Sum_Spend": 15, "Names": "Ada|Alan"},
        {"City": "B", "Sum_Spend": 7, "Names": "Grace"},
    ]


def test_summarize_defers_spatial_actions(workflow_context):
    with pytest.raises(NotImplementedError, match="deferred"):
        summarize_tool(
            {"Input": pd.DataFrame({"SpatialObj": ["x"]})},
            {"summarize_fields": [{"field": "SpatialObj", "action": "SpatialObjCombine", "rename": "Spatial"}]},
            workflow_context,
        )
