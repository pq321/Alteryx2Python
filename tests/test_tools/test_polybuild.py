import pandas as pd

from alteryx2python.tools.polybuild import polybuild_tool


def test_polybuild_sequence_polygon_orders_points_by_sequence(workflow_context):
    frame = pd.DataFrame(
        {
            "Store Num": ["A", "A", "A"],
            "Split_SequenceNum": [2, 1, 3],
            "Split_SpatialObj": ["POINT (1 0)", "POINT (0 0)", "POINT (0 1)"],
        }
    )

    output = polybuild_tool(
        {"Input": frame},
        {
            "spatial_field": "Split_SpatialObj",
            "group_field": "Store Num",
            "sequence_field": "Split_SequenceNum",
            "build_type": "SequencePolygon",
        },
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [
        {"Store Num": "A", "SpatialObj_Built": "POLYGON ((0 0, 1 0, 0 1, 0 0))"}
    ]


def test_polybuild_convex_hull_outputs_grouped_polygon(workflow_context):
    frame = pd.DataFrame(
        {
            "RecordID": [1, 1, 1, 1],
            "Centroid": ["POINT (0 0)", "POINT (1 0)", "POINT (0.5 0.5)", "POINT (0 1)"],
        }
    )

    output = polybuild_tool(
        {"Input": frame},
        {"spatial_field": "Centroid", "group_field": "RecordID", "build_type": "ConvexHull"},
        workflow_context,
    )["Output"]

    assert output.loc[0, "RecordID"] == 1
    assert output.loc[0, "SpatialObj_Built"] == "POLYGON ((0 0, 1 0, 0 1, 0 0))"
