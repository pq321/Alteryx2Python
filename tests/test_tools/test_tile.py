import pandas as pd

from alteryx2python.tools.tile import tile_tool


def test_tile_equal_records_assigns_tiles(workflow_context):
    output = tile_tool(
        {"Input": pd.DataFrame({"value": [10, 20, 30, 40]})},
        {"method": "EqualRecords", "num_tiles": 2},
        workflow_context,
    )["Output"]

    assert output["Tile_Num"].tolist() == [1, 1, 2, 2]


def test_tile_manual_cutoffs_assigns_bins(workflow_context):
    output = tile_tool(
        {"Input": pd.DataFrame({"AVERAGE SALE": [5, 25, 75, 125]})},
        {"method": "Manual", "field": "AVERAGE SALE", "cutoffs": [10, 50, 100]},
        workflow_context,
    )["Output"]

    assert output["Tile_Num"].tolist() == [1, 2, 3, 4]
