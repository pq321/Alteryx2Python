import pandas as pd

from alteryx2python.tools.generalize import generalize_tool


def test_generalize_outputs_deduped_spatial_field_and_can_omit_source(workflow_context):
    frame = pd.DataFrame({"id": [1], "SpatialObj": ["LINESTRING (0 0, 0 0, 2 2)"]})

    output = generalize_tool(
        {"Input": frame},
        {"spatial_field": "SpatialObj", "include_source": False, "output_field": "SpatialObj_Generalize"},
        workflow_context,
    )["Output"]

    assert list(output.columns) == ["id", "SpatialObj_Generalize"]
    assert output.loc[0, "SpatialObj_Generalize"] == "LINESTRING (0 0, 2 2)"
