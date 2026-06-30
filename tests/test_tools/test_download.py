import pandas as pd
import pytest

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.download import DownloadTool, download_tool


def test_download_posts_field_payload_and_appends_response_columns(workflow_context):
    requests = []

    def transport(request):
        requests.append(request)
        return {"body": '{"ok":true}', "headers": {"x-request-id": "abc"}}

    frame = pd.DataFrame(
        {
            "id": [1],
            "URL": ["https://example.test/api"],
            "JSON": ['{"id":1}'],
        }
    )

    result = download_tool(
        {"Input": frame},
        {
            "node_id": "16",
            "source_tool_id": "16",
            "url_field": "URL",
            "output_mode": "String",
            "headers": [{"name": "Content-Type", "value": "application/json"}],
            "payload": {"http_action": "POST", "body_mode": "Field", "field": "JSON"},
            "timeout": 600,
            "transport": transport,
        },
        workflow_context,
    )

    assert requests == [
        {
            "method": "POST",
            "url": "https://example.test/api",
            "headers": {"Content-Type": "application/json"},
            "body": '{"id":1}',
            "timeout": 600,
        }
    ]
    output = result["Output"]
    assert list(output.columns) == ["id", "URL", "JSON", "DownloadData", "DownloadHeaders"]
    assert output.to_dict("records") == [
        {
            "id": 1,
            "URL": "https://example.test/api",
            "JSON": '{"id":1}',
            "DownloadData": '{"ok":true}',
            "DownloadHeaders": '{"x-request-id": "abc"}',
        }
    ]
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "Download"
    assert trace["outputs"]["Output"]["columns"] == ["id", "URL", "JSON", "DownloadData", "DownloadHeaders"]


def test_download_uses_runtime_transport_when_config_transport_is_absent():
    context = WorkflowContext(
        runtime_config={"download_transport": lambda request: {"body": "ok", "headers": ""}}
    )
    frame = pd.DataFrame({"URL": ["https://example.test"]})

    output = download_tool(
        {"Input": frame},
        {"url_field": "URL", "payload": {"http_action": "GET"}},
        context,
    )["Output"]

    assert output["DownloadData"].tolist() == ["ok"]


def test_download_requires_explicit_transport_or_network_opt_in(workflow_context):
    with pytest.raises(RuntimeError, match="requires an injected transport"):
        download_tool(
            {"Input": pd.DataFrame({"URL": ["https://example.test"]})},
            {"url_field": "URL"},
            workflow_context,
        )


def test_download_rejects_non_string_output_mode(workflow_context):
    with pytest.raises(NotImplementedError, match="String output mode"):
        download_tool(
            {"Input": pd.DataFrame({"URL": ["https://example.test"]})},
            {"url_field": "URL", "output_mode": "Blob", "transport": lambda request: {}},
            workflow_context,
        )


def test_download_tool_class_executes_same_contract(workflow_context):
    tool = DownloadTool()

    result = tool.execute(
        {"Input": pd.DataFrame({"URL": ["https://example.test"]})},
        {"url_field": "URL", "transport": lambda request: {"body": "ok", "headers": {}}},
        workflow_context,
    )

    assert isinstance(result["Output"], pd.DataFrame)
