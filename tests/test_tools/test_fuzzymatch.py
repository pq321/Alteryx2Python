import pandas as pd
import pytest

from alteryx2python.tools.fuzzymatch import FuzzyMatchTool, fuzzymatch_tool


def test_fuzzymatch_emits_pairs_for_equal_values(workflow_context):
    frame = pd.DataFrame({"transaction_id": [11, 7, 10, 12], "acct_holder": ["Acme", "Acme Inc", "ACME", None]})

    output = fuzzymatch_tool(
        {"Input": frame},
        {
            "record_id_field": "transaction_id",
            "output_score": True,
            "match_fields": [{"field_name": "acct_holder"}],
        },
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [{"transaction_id": 10, "transaction_id2": 11, "MatchScore": 100.0}]


def test_fuzzymatch_rejects_missing_input(workflow_context):
    with pytest.raises(KeyError, match="requires an Input anchor"):
        fuzzymatch_tool({}, {}, workflow_context)


def test_fuzzymatch_tool_class_executes_same_contract(workflow_context):
    result = FuzzyMatchTool().execute(
        {"Input": pd.DataFrame({"id": [1, 2, 3], "phone": ["(12) 345", "123-45", "123-45"], "source": ["A", "A", "B"]})},
        {"record_id_field": "id", "source_id_field": "source", "merge_mode": True,
         "match_fields": [{"field_name": "phone", "key_function": "DigitsReverse"}]},
        workflow_context,
    )

    assert result["Output"].to_dict("records") == [{"id": 1, "id2": 3}, {"id": 2, "id2": 3}]


def test_fuzzymatch_rejects_unimplemented_scoring(workflow_context):
    with pytest.raises(NotImplementedError, match="DblMetaphone / JaroTFIDF"):
        fuzzymatch_tool(
            {"Input": pd.DataFrame({"id": [1], "name": ["A"]})},
            {"record_id_field": "id", "match_fields": [
                {"field_name": "name", "key_function": "DblMetaphone", "match_function": "JaroTFIDF"}
            ]},
            workflow_context,
        )
