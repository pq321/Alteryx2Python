import pandas as pd

from alteryx2python.tools.rank import rank_tool


def test_rank_ordinal_descending(workflow_context):
    frame = pd.DataFrame({"Record": [1, 2, 3], "Units Sold": [10, 20, 20]})

    output = rank_tool(
        {"Input": frame},
        {"ranking_modes": ["Ordinal"], "sort_fields": [{"field": "Units Sold", "order": "Descending"}]},
        workflow_context,
    )["Output"]

    assert output["Record"].tolist() == [2, 3, 1]
    assert output["Rank"].tolist() == [1, 2, 3]


def test_rank_dense_resets_by_group(workflow_context):
    frame = pd.DataFrame({"Group": ["A", "A", "B"], "Units Sold": [20, 10, 20]})

    output = rank_tool(
        {"Input": frame},
        {
            "ranking_modes": ["Dense"],
            "sort_fields": [{"field": "Units Sold", "order": "Descending"}],
            "group_fields": ["Group"],
        },
        workflow_context,
    )["Output"]

    assert output["Rank"].tolist() == [1, 1, 2]
