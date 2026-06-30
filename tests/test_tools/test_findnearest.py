import pytest
import pandas as pd

from alteryx2python.tools.findnearest import findnearest_tool


def test_findnearest_outputs_rank_distance_direction_and_selected_fields(workflow_context):
    targets = pd.DataFrame({"Store": ["A"], "Store Point": ["POINT (0 0)"]})
    universe = pd.DataFrame(
        {
            "Name": ["Near", "Far"],
            "SpatialObj": ["POINT (1 0)", "POINT (4 0)"],
        }
    )

    output = findnearest_tool(
        {"Targets": targets, "Universe": universe},
        {
            "target_spatial_field": "Store Point",
            "universe_spatial_field": "SpatialObj",
            "how_many": 1,
            "max_distance": 200,
            "max_distance_units": "Miles",
            "select_fields": [
                {"source": "Target_Store", "selected": True},
                {"source": "Universe_Name", "rename": "Closest", "selected": True},
                {"source": "FindNearestRank", "selected": True},
                {"source": "DistanceMiles", "selected": True},
                {"source": "Direction", "selected": True},
            ],
        },
        workflow_context,
    )["Matched"]

    assert output.to_dict("records")[0]["Closest"] == "Near"
    assert output.loc[0, "FindNearestRank"] == 1
    assert output.loc[0, "DistanceMiles"] == pytest.approx(69.09, rel=1e-3)
    assert output.loc[0, "Direction"] == "E"


def test_findnearest_respects_how_many_and_max_distance(workflow_context):
    targets = pd.DataFrame({"Store Point": ["POINT (0 0)"]})
    universe = pd.DataFrame({"SpatialObj": ["POINT (1 0)", "POINT (2 0)", "POINT (10 0)"]})

    output = findnearest_tool(
        {"Targets": targets, "Universe": universe},
        {
            "target_spatial_field": "Store Point",
            "universe_spatial_field": "SpatialObj",
            "how_many": 3,
            "max_distance": 150,
            "max_distance_units": "Miles",
        },
        workflow_context,
    )["Matched"]

    assert output["FindNearestRank"].tolist() == [1, 2]
