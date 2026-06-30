import pandas as pd

from alteryx2python.tools.smooth import smooth_tool


def test_smooth_outputs_smoothed_field_and_can_omit_source(workflow_context):
    frame = pd.DataFrame({"id": [1], "SpatialObj_Generalize": ["LINESTRING (0 0, 3 0, 3 3)"]})

    output = smooth_tool(
        {"Input": frame},
        {
            "spatial_field": "SpatialObj_Generalize",
            "include_source": False,
            "passes": "1",
            "output_field": "SpatialObj_Smooth",
        },
        workflow_context,
    )["Output"]

    assert list(output.columns) == ["id", "SpatialObj_Smooth"]
    assert output.loc[0, "SpatialObj_Smooth"] == "LINESTRING (0 0, 2 1, 3 3)"
