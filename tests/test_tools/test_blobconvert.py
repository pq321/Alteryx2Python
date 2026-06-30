import base64
import hashlib

import pandas as pd

from alteryx2python.tools.blobconvert import blobconvert_tool


def test_blobconvert_blob_to_base64_and_hex(workflow_context):
    frame = pd.DataFrame({"Blob": [b"hello"]})

    base64_output = blobconvert_tool(
        {"Input": frame},
        {"field": "Blob", "mode": "Base64", "to_blob": False},
        workflow_context,
    )["Output"]
    hex_output = blobconvert_tool(
        {"Input": frame},
        {"field": "Blob", "mode": "Hex", "to_blob": False},
        workflow_context,
    )["Output"]

    assert base64_output.loc[0, "Blob"] == base64.b64encode(b"hello").decode("ascii")
    assert hex_output.loc[0, "Blob"] == "68656C6C6F"


def test_blobconvert_blob_to_md5_and_report_snippet(workflow_context):
    frame = pd.DataFrame({"Blob": [b"hello"]})

    md5_output = blobconvert_tool(
        {"Input": frame},
        {"field": "Blob", "mode": "MD5", "to_blob": False},
        workflow_context,
    )["Output"]
    snippet_output = blobconvert_tool(
        {"Input": frame},
        {"field": "Blob", "mode": "ReportSnippet", "to_blob": False},
        workflow_context,
    )["Output"]

    assert md5_output.loc[0, "Blob"] == hashlib.md5(b"hello").hexdigest()
    assert snippet_output.loc[0, "Blob"].startswith('<img src="data:application/octet-stream;base64,')


def test_blobconvert_text_to_blob_roundtrip_utf16(workflow_context):
    frame = pd.DataFrame({"Field1": ["hello"]})

    blob_output = blobconvert_tool(
        {"Input": frame},
        {"field": "Field1", "mode": "Text", "to_blob": True, "text_code_page": "UTF16"},
        workflow_context,
    )["Output"]
    text_output = blobconvert_tool(
        {"Input": blob_output},
        {"field": "Field1", "mode": "Text", "to_blob": False, "text_code_page": "UTF16"},
        workflow_context,
    )["Output"]

    assert isinstance(blob_output.loc[0, "Field1"], bytes)
    assert text_output.loc[0, "Field1"] == "hello"


def test_blobconvert_base64_to_blob(workflow_context):
    encoded = base64.b64encode(b"hello").decode("ascii")

    result = blobconvert_tool(
        {"Input": pd.DataFrame({"payload": [encoded]})},
        {"field": "payload", "mode": "Base64", "to_blob": True},
        workflow_context,
    )

    assert result["Output"].loc[0, "payload"] == b"hello"
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "BlobConvert"
