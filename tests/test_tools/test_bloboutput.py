import pandas as pd
import pytest

from alteryx2python.tools.bloboutput import BlobOutputTool, bloboutput_tool


def test_bloboutput_records_external_write_without_writing(workflow_context):
    frame = pd.DataFrame({"FileName": ["a.bin"], "Blob": [b"abc"]})

    result = bloboutput_tool(
        {"Input": frame},
        {"file_name": "%TEMP%/BlobOutput", "blob_field": "Blob"},
        workflow_context,
    )

    assert result == {}
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "BlobOutput"
    assert trace["config"]["blob_field"] == "Blob"
    assert trace["config"]["external_write_performed"] is False


def test_bloboutput_rejects_missing_input(workflow_context):
    with pytest.raises(KeyError, match="requires an Input anchor"):
        bloboutput_tool({}, {}, workflow_context)


def test_bloboutput_tool_class_executes_same_contract(workflow_context):
    result = BlobOutputTool().execute({"Input": pd.DataFrame({"Blob": [b"x"]})}, {}, workflow_context)

    assert result == {}
