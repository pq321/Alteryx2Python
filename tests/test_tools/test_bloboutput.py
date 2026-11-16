import pandas as pd
import pytest

from alteryx2python.tools.bloboutput import BlobOutputTool, bloboutput_tool


def test_bloboutput_writes_each_named_blob(workflow_context, tmp_path):
    frame = pd.DataFrame({"FileName": ["a.bin", "b.bin"], "Blob": [b"abc", b"\x00\xff"]})

    result = bloboutput_tool(
        {"Input": frame},
        {"file_name": "subdir/template.bin", "blob_field": "Blob", "base_dir": str(tmp_path),
         "modify_method": "FileName", "modify_filename_field": "FileName"},
        workflow_context,
    )

    assert result == {}
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "BlobOutput"
    assert trace["config"]["blob_field"] == "Blob"
    assert trace["config"]["external_write_performed"] is True
    assert (tmp_path / "subdir/a.bin").read_bytes() == b"abc"
    assert (tmp_path / "subdir/b.bin").read_bytes() == b"\x00\xff"


def test_bloboutput_rejects_missing_input(workflow_context):
    with pytest.raises(KeyError, match="requires an Input anchor"):
        bloboutput_tool({}, {}, workflow_context)


def test_bloboutput_tool_class_executes_same_contract(workflow_context, tmp_path):
    target = tmp_path / "blob.bin"
    result = BlobOutputTool().execute(
        {"Input": pd.DataFrame({"Blob": [b"x"]})},
        {"file_name": str(target), "blob_field": "Blob"}, workflow_context,
    )

    assert result == {}
    assert target.read_bytes() == b"x"
