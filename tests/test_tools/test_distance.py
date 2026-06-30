import pytest
import pandas as pd

from alteryx2python.tools.distance import distance_tool


def test_distance_outputs_haversine_miles(workflow_context):
    frame = pd.DataFrame({"Source": ["POINT (0 0)"], "Dest": ["POINT (1 0)"]})

    output = distance_tool(
        {"Input": frame},
        {
            "source_spatial_field": "Source",
            "destination_spatial_field": "Dest",
            "output_distance": True,
            "output_units": "Miles",
        },
        workflow_context,
    )["Output"]

    assert output.loc[0, "DistanceMiles"] == pytest.approx(69.09, rel=1e-3)


def test_distance_outputs_direction_fields(workflow_context):
    frame = pd.DataFrame({"Source": ["POINT (0 0)"], "Dest": ["POINT (1 1)"]})

    output = distance_tool(
        {"Input": frame},
        {
            "source_spatial_field": "Source",
            "destination_spatial_field": "Dest",
            "output_distance": True,
            "output_cardinal_direction": True,
            "output_direction_degrees": True,
            "output_units": "Miles",
        },
        workflow_context,
    )["Output"]

    assert output.loc[0, "Direction"] == "NE"
    assert output.loc[0, "DirectionDegrees"] == pytest.approx(44.9956, rel=1e-4)


def test_distance_drive_time_mode_uses_straight_line_distance_baseline(workflow_context):
    frame = pd.DataFrame({"Source": ["POINT (0 0)"], "Dest": ["POINT (0 1)"]})

    output = distance_tool(
        {"Input": frame},
        {
            "source_spatial_field": "Source",
            "destination_spatial_field": "Dest",
            "output_drive_time_and_distance": True,
            "output_units": "Miles",
        },
        workflow_context,
    )["Output"]

    assert output.loc[0, "DriveDistanceMiles"] == pytest.approx(69.09, rel=1e-3)
    assert pd.isna(output.loc[0, "DriveTimeMinutes"])
