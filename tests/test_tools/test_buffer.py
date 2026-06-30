import pandas as pd

from alteryx2python.tools.buffer import buffer_tool


def test_buffer_expands_polygon_bbox_with_specific_value(workflow_context):
    frame = pd.DataFrame({"SpatialObj": ["POLYGON ((0 1, 1 1, 1 0, 0 0, 0 1))"]})

    output = buffer_tool(
        {"Input": frame},
        {
            "spatial_field": "SpatialObj",
            "include_source": True,
            "buffer_size_source": "SpecificValue",
            "buffer_size": "69",
            "units": "Miles",
        },
        workflow_context,
    )["Output"]

    assert output.loc[0, "SpatialObj_Buffer"] == "POLYGON ((-1 2, 2 2, 2 -1, -1 -1, -1 2))"
    assert "SpatialObj" in output.columns


def test_buffer_can_omit_source_spatial_field_and_use_field_radius(workflow_context):
    frame = pd.DataFrame({"id": [1], "radius": [69], "SpatialObj": ["POLYGON ((0 1, 1 1, 1 0, 0 0, 0 1))"]})

    output = buffer_tool(
        {"Input": frame},
        {
            "spatial_field": "SpatialObj",
            "include_source": False,
            "buffer_size_source": "Field",
            "buffer_size_field": "radius",
            "units": "Miles",
        },
        workflow_context,
    )["Output"]

    assert "SpatialObj" not in output.columns
    assert output.loc[0, "SpatialObj_Buffer"] == "POLYGON ((-1 2, 2 2, 2 -1, -1 -1, -1 2))"
