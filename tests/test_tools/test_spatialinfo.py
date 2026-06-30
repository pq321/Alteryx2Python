import pandas as pd

from alteryx2python.tools.spatialinfo import spatialinfo_tool


def test_spatialinfo_outputs_area_and_centroid_fields(workflow_context):
    frame = pd.DataFrame({"SpatialObj": ["POLYGON ((0 0, 4 0, 4 2, 0 2, 0 0))"]})

    output = spatialinfo_tool(
        {"Input": frame},
        {"spatial_field": "SpatialObj", "selected_items": ["AreaMi", "CentroidObj", "CentroidXY"]},
        workflow_context,
    )["Output"]

    assert output.loc[0, "AreaSqMi"] == 8.0
    assert output.loc[0, "Centroid"] == "POINT (2 1)"
    assert output.loc[0, "CentroidX"] == 2.0
    assert output.loc[0, "CentroidY"] == 1.0


def test_spatialinfo_outputs_bounding_rectangle_and_endpoints(workflow_context):
    frame = pd.DataFrame({"SpatialObj": ["LINESTRING (1 2, 5 6, 3 1)"]})

    output = spatialinfo_tool(
        {"Input": frame},
        {"spatial_field": "SpatialObj", "selected_items": ["RectObj", "RectPolygon", "RectXY", "EndPointsObj", "EndPointsXY"]},
        workflow_context,
    )["Output"]

    assert output.loc[0, "BoundingRect_TopLeft"] == "POINT (1 6)"
    assert output.loc[0, "BoundingRect_BottomRight"] == "POINT (5 1)"
    assert output.loc[0, "BoundingRect"] == "POLYGON ((1 6, 5 6, 5 1, 1 1, 1 6))"
    assert output.loc[0, "BR_TopLeft_X"] == 1.0
    assert output.loc[0, "BR_BottomRight_Y"] == 1.0
    assert output.loc[0, "StartPoint"] == "POINT (1 2)"
    assert output.loc[0, "EndPoint"] == "POINT (3 1)"
