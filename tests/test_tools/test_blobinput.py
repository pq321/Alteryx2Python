import pandas as pd
import pytest

from alteryx2python.tools.blobinput import BlobInputTool, blobinput_tool


def test_blobinput_reads_configured_file(tmp_path, workflow_context):
    path = tmp_path / "image.bin"
    path.write_bytes(b"abcdef")

    output = blobinput_tool({}, {"file_name": str(path)}, workflow_context)["Output"]

    assert output[["FileName", "FullPath", "Blob"]].to_dict("records") == [
        {"FileName": str(path), "FullPath": str(path), "Blob": b"abcdef"}
    ]


def test_blobinput_splits_blobs_into_chunks(tmp_path, workflow_context):
    path = tmp_path / "image.bin"
    path.write_bytes(b"abcdef")

    output = blobinput_tool(
        {},
        {"file_name": str(path), "split_blobs": True, "blob_chunk_size": "2"},
        workflow_context,
    )["Output"]

    assert output["Blob"].tolist() == [b"ab", b"cd", b"ef"]
    assert output["BlobChunkID"].tolist() == [1, 2, 3]


def test_blobinput_uses_filename_field_from_input(tmp_path, workflow_context):
    path = tmp_path / "image.bin"
    path.write_bytes(b"x")

    output = BlobInputTool().execute(
        {"Input": pd.DataFrame({"FullPath": [str(path)]})},
        {"modify_filename_field": "FullPath"},
        workflow_context,
    )["Output"]

    assert output["Blob"].tolist() == [b"x"]


def test_blobinput_entire_path_does_not_fall_back_to_template(tmp_path, workflow_context):
    template = tmp_path / "template.xlsm"
    template.write_bytes(b"template")
    missing = tmp_path / "missing.xlsm"
    with pytest.raises(FileNotFoundError) as failure:
        blobinput_tool(
            {"Input": pd.DataFrame({"SourcePath": [str(missing)]})},
            {"file_name": str(template), "modify_method": "Path", "modify_filename_field": "SourcePath",
             "stop_on_error": True, "native_output": True},
            workflow_context,
        )
    assert failure.value.filename == str(missing)
