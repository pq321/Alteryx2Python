import pandas as pd

from alteryx2python.tools.spatialmatch import spatialmatch_tool


def test_spatialmatch_intersects_outputs_selected_prefixed_fields(workflow_context):
    targets = pd.DataFrame(
        {
            "Store": ["A"],
            "SpatialObject_TradeArea": ["POLYGON ((0 3, 3 3, 3 0, 0 0, 0 3))"],
            "RadiusSize": ["3"],
        }
    )
    universe = pd.DataFrame({"Name": ["Inside", "Outside"], "SpatialObj": ["POINT (1 1)", "POINT (9 9)"]})

    output = spatialmatch_tool(
        {"Targets": targets, "Universe": universe},
        {
            "target_spatial_field": "SpatialObject_TradeArea",
            "universe_spatial_field": "SpatialObj",
            "method": "Intersects",
            "intersect_poly": True,
            "select_fields": [
                {"source": "Target_SpatialObject_TradeArea", "rename": "StoreSpObj", "selected": True},
                {"source": "Universe_Name", "rename": "AdAreaName", "selected": True},
                {"source": "*Unknown", "selected": True},
            ],
        },
        workflow_context,
    )["Matched"]

    assert output["AdAreaName"].tolist() == ["Inside"]
    assert output.loc[0, "StoreSpObj"].startswith("POLYGON")
    assert output.loc[0, "IntersectPoly"].startswith("POLYGON")
    assert "Target_RadiusSize" in output.columns


def test_spatialmatch_contains_and_within_use_bbox_direction(workflow_context):
    targets = pd.DataFrame({"TargetObj": ["POLYGON ((0 4, 4 4, 4 0, 0 0, 0 4))"]})
    universe = pd.DataFrame({"UniverseObj": ["POINT (2 2)", "POINT (5 5)"]})

    contains = spatialmatch_tool(
        {"Targets": targets, "Universe": universe},
        {"target_spatial_field": "TargetObj", "universe_spatial_field": "UniverseObj", "method": "Contains"},
        workflow_context,
    )["Matched"]
    within = spatialmatch_tool(
        {"Targets": universe.rename(columns={"UniverseObj": "TargetObj"}), "Universe": targets.rename(columns={"TargetObj": "UniverseObj"})},
        {"target_spatial_field": "TargetObj", "universe_spatial_field": "UniverseObj", "method": "Within"},
        workflow_context,
    )["Matched"]

    assert len(contains.index) == 1
    assert len(within.index) == 1
