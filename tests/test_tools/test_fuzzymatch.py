import pandas as pd
import pytest

from alteryx2python.tools.fuzzymatch import FuzzyMatchTool, fuzzymatch_tool


def test_fuzzymatch_passes_input_with_optional_metadata(workflow_context):
    frame = pd.DataFrame({"transaction_id": [10, 11], "acct_holder": ["Acme", "Acme Inc"]})

    output = fuzzymatch_tool(
        {"Input": frame},
        {
            "record_id_field": "transaction_id",
            "output_score": True,
            "output_key": True,
            "match_fields": [{"field_name": "acct_holder"}],
        },
        workflow_context,
    )["Output"]

    assert output["FuzzyMatchGroupID"].tolist() == [10, 11]
    assert output["FuzzyMatchScore"].tolist() == [100.0, 100.0]
    assert output["FuzzyMatchKey"].tolist() == ["Acme", "Acme Inc"]


def test_fuzzymatch_rejects_missing_input(workflow_context):
    with pytest.raises(KeyError, match="requires an Input anchor"):
        fuzzymatch_tool({}, {}, workflow_context)


def test_fuzzymatch_tool_class_executes_same_contract(workflow_context):
    result = FuzzyMatchTool().execute({"Input": pd.DataFrame({"id": [1]})}, {}, workflow_context)

    assert result["Output"]["id"].tolist() == [1]
