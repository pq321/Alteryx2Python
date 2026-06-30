import pandas as pd
import pytest

from alteryx2python.tools.makegroup import MakeGroupTool, makegroup_tool


def test_makegroup_assigns_connected_group_ids(workflow_context):
    frame = pd.DataFrame({"key_A": ["A", "B", "C"], "key_B": ["B", "C", "D"]})

    output = makegroup_tool(
        {"Input": frame},
        {"key_first": "key_A", "key_second": "key_B"},
        workflow_context,
    )["Output"]

    assert output["GroupID"].tolist() == [1, 1, 1]


def test_makegroup_rejects_missing_key_field(workflow_context):
    with pytest.raises(KeyError):
        makegroup_tool({"Input": pd.DataFrame({"key_A": ["A"]})}, {"key_first": "key_A", "key_second": "key_B"}, workflow_context)


def test_makegroup_tool_class_executes_same_contract(workflow_context):
    result = MakeGroupTool().execute(
        {"Input": pd.DataFrame({"a": ["x"], "b": ["y"]})},
        {"key_first": "a", "key_second": "b"},
        workflow_context,
    )

    assert result["Output"]["GroupID"].tolist() == [1]
