import pandas as pd
import pytest

from alteryx2python.tools.createpoints import createpoints_tool


def test_createpoints_outputs_wkt_points(workflow_context):
    frame = pd.DataFrame(
        {
            "Name": ["A", "B"],
            "Lon": [-73.9857, "-118.2437"],
            "Lat": [40.7484, "34.0522"],
        }
    )

    result = createpoints_tool(
        {"Input": frame},
        {"x_field": "Lon", "y_field": "Lat", "mode": "Double"},
        workflow_context,
    )

    output = result["Output"]
    assert output["Centroid"].tolist() == [
        "POINT (-73.9857 40.7484)",
        "POINT (-118.244 34.0522)",
    ]
    assert output[["Name", "Lon", "Lat"]].equals(frame)
    assert workflow_context.traces[-1].tool_type == "CreatePoints"


def test_createpoints_uses_configured_output_field_and_nulls_bad_coordinates(workflow_context):
    result = createpoints_tool(
        {"Input": pd.DataFrame({"x": [1, "bad"], "y": [2, 3]})},
        {"x_field": "x", "y_field": "y", "output_field": "Location"},
        workflow_context,
    )

    assert result["Output"].loc[0, "Location"] == "POINT (1 2)"
    assert pd.isna(result["Output"].loc[1, "Location"])


def test_createpoints_rejects_unsupported_mode(workflow_context):
    with pytest.raises(NotImplementedError, match="mode"):
        createpoints_tool(
            {"Input": pd.DataFrame({"x": [1], "y": [2]})},
            {"x_field": "x", "y_field": "y", "mode": "DMS"},
            workflow_context,
        )
