import pandas as pd
import pytest

from alteryx2python.tools.makegrid import MakeGridTool, makegrid_tool


def test_makegrid_adds_bbox_grid_metadata(workflow_context):
    frame = pd.DataFrame({"SpatialObj": ["POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"]})

    output = makegrid_tool(
        {"Input": frame},
        {"spatial_field": "SpatialObj", "grid_size": "1", "units": "Miles"},
        workflow_context,
    )["Output"]

    assert output["Grid"].tolist() == ["POLYGON ((0 1, 1 1, 1 0, 0 0, 0 1))"]
    assert output["GridSize"].tolist() == ["1"]
    assert output["GridUnits"].tolist() == ["Miles"]


def test_makegrid_rejects_missing_spatial_field(workflow_context):
    with pytest.raises(KeyError):
        makegrid_tool({"Input": pd.DataFrame({"a": [1]})}, {"spatial_field": "Missing"}, workflow_context)


def test_makegrid_tool_class_executes_same_contract(workflow_context):
    result = MakeGridTool().execute(
        {"Input": pd.DataFrame({"SpatialObj": ["POINT (0 0)"]})},
        {"spatial_field": "SpatialObj"},
        workflow_context,
    )

    assert result["Output"]["Grid"].tolist() == ["POLYGON ((0 0, 0 0, 0 0, 0 0, 0 0))"]
