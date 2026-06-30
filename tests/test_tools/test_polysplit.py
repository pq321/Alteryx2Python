import pandas as pd
import pytest

from alteryx2python.tools.polysplit import PolySplitTool, polysplit_tool


def test_polysplit_outputs_point_rows_for_polygon_vertices(workflow_context):
    frame = pd.DataFrame({"SpatialObject": ["POLYGON ((0 0, 1 0, 0 1, 0 0))"], "Name": ["A"]})

    output = polysplit_tool(
        {"Input": frame},
        {"spatial_field": "SpatialObject", "split_to": "Point"},
        workflow_context,
    )["Output"]

    assert output[["Name", "Split_SequenceNum", "Split_SpatialObj", "Split_OriginalRecordID"]].to_dict(
        "records"
    ) == [
        {"Name": "A", "Split_SequenceNum": 1, "Split_SpatialObj": "POINT (0 0)", "Split_OriginalRecordID": 1},
        {"Name": "A", "Split_SequenceNum": 2, "Split_SpatialObj": "POINT (1 0)", "Split_OriginalRecordID": 1},
        {"Name": "A", "Split_SequenceNum": 3, "Split_SpatialObj": "POINT (0 1)", "Split_OriginalRecordID": 1},
        {"Name": "A", "Split_SequenceNum": 4, "Split_SpatialObj": "POINT (0 0)", "Split_OriginalRecordID": 1},
    ]


def test_polysplit_rejects_missing_spatial_field(workflow_context):
    with pytest.raises(KeyError):
        polysplit_tool({"Input": pd.DataFrame({"a": [1]})}, {"spatial_field": "Missing"}, workflow_context)


def test_polysplit_tool_class_executes_same_contract(workflow_context):
    result = PolySplitTool().execute(
        {"Input": pd.DataFrame({"SpatialObject": ["LINESTRING (0 0, 1 1)"]})},
        {"spatial_field": "SpatialObject"},
        workflow_context,
    )

    assert result["Output"]["Split_SequenceNum"].tolist() == [1, 2]
