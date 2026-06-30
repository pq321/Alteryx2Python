import pandas as pd
import pytest

from alteryx2python.tools.blockuntildone import BlockUntilDoneTool, blockuntildone_tool


def test_blockuntildone_copies_input_to_three_outputs(workflow_context):
    frame = pd.DataFrame({"a": [1, 2]})

    result = blockuntildone_tool({"Input": frame}, {"node_id": "13"}, workflow_context)

    assert set(result) == {"Output", "Output2", "Output3"}
    assert result["Output"].to_dict("records") == [{"a": 1}, {"a": 2}]
    assert result["Output2"].to_dict("records") == [{"a": 1}, {"a": 2}]
    assert result["Output3"].to_dict("records") == [{"a": 1}, {"a": 2}]
    assert result["Output"] is not frame
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "BlockUntilDone"
    assert trace["outputs"]["Output3"]["row_count"] == 2


def test_blockuntildone_rejects_missing_input(workflow_context):
    with pytest.raises(KeyError, match="requires an Input anchor"):
        blockuntildone_tool({}, {}, workflow_context)


def test_blockuntildone_tool_class_executes_same_contract(workflow_context):
    result = BlockUntilDoneTool().execute(
        {"Input": pd.DataFrame({"a": [1]})},
        {},
        workflow_context,
    )

    assert result["Output"]["a"].tolist() == [1]
