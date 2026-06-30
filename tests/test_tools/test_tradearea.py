import pandas as pd
import pytest

from alteryx2python.tools.tradearea import tradearea_tool


def test_tradearea_outputs_one_row_per_radius(workflow_context):
    frame = pd.DataFrame({"Store": ["A"], "Store Point": ["POINT (-105 40)"]})

    output = tradearea_tool(
        {"Input": frame},
        {"spatial_field": "Store Point", "include_source": True, "units": "Miles", "radii": "15, 10, 5"},
        workflow_context,
    )["Output"]

    assert output["RadiusSize"].tolist() == ["15", "10", "5"]
    assert output["Store"].tolist() == ["A", "A", "A"]
    assert output["SpatialObject_TradeArea"].str.startswith("POLYGON ((").all()
    assert "Store Point" in output.columns


def test_tradearea_respects_include_source_false_and_radius_ranges(workflow_context):
    output = tradearea_tool(
        {"Input": pd.DataFrame({"Centroid": ["POINT (0 0)"]})},
        {"spatial_field": "Centroid", "include_source": False, "units": "Miles", "radii": "2-5, 7-10"},
        workflow_context,
    )["Output"]

    assert "Centroid" not in output.columns
    assert output["RadiusSize"].tolist() == ["2-5", "7-10"]
    assert output["SpatialObject_TradeArea"].notna().all()


def test_tradearea_defer_radius_from_field_mode(workflow_context):
    with pytest.raises(NotImplementedError, match="radius-from-field"):
        tradearea_tool(
            {"Input": pd.DataFrame({"SpatialObj": ["POINT (0 0)"]})},
            {"spatial_field": "SpatialObj", "radius_from_field": True, "radii": ""},
            workflow_context,
        )
