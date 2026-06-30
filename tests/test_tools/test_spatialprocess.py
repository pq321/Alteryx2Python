import pandas as pd

from alteryx2python.tools.spatialprocess import spatialprocess_tool


def test_spatialprocess_cut_from_second_outputs_process_field(workflow_context):
    frame = pd.DataFrame(
        {
            "StoreSpObj": ["POLYGON ((0 1, 1 1, 1 0, 0 0, 0 1))"],
            "AdArea": ["POLYGON ((0 2, 2 2, 2 0, 0 0, 0 2))"],
        }
    )

    output = spatialprocess_tool(
        {"Input": frame},
        {
            "field1": "StoreSpObj",
            "field2": "AdArea",
            "action": "Cut1_From2",
            "output_field": "SpatialObj_Process",
        },
        workflow_context,
    )["Output"]

    assert output.loc[0, "SpatialObj_Process"] == frame.loc[0, "AdArea"]


def test_spatialprocess_no_empty_filters_empty_results(workflow_context):
    frame = pd.DataFrame({"Left": [""], "Right": [""]})

    output = spatialprocess_tool(
        {"Input": frame},
        {"field1": "Left", "field2": "Right", "action": "Cut1_From2", "no_empty": True},
        workflow_context,
    )["Output"]

    assert output.empty
