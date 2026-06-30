from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


DownloadTransport = Callable[[dict[str, Any]], dict[str, Any]]


def _configured_headers(config: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in config.get("headers", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name:
            headers[name] = str(item.get("value", ""))
    return headers


def _payload_body(row: dict[str, Any], config: dict[str, Any]) -> str | bytes | None:
    payload = config.get("payload")
    if not isinstance(payload, dict):
        return None
    body_mode = str(payload.get("body_mode", ""))
    field = str(payload.get("field", ""))
    if body_mode.lower() != "field" or not field:
        return None
    if field not in row:
        raise KeyError(f"Missing Download payload field: {field}")
    value = row[field]
    if pd.isna(value):
        return ""
    return str(value)


def _encode_url_if_requested(url: str, config: dict[str, Any]) -> str:
    if not config.get("encode_urls", False):
        return url
    return quote(url, safe=":/?&=%#[]@!$&'()*+,;")


def _response_headers(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _response_body(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _default_transport(request: dict[str, Any]) -> dict[str, Any]:
    body = request.get("body")
    data = body.encode("utf-8") if isinstance(body, str) else body
    http_request = Request(
        str(request["url"]),
        data=data,
        headers=dict(request.get("headers", {})),
        method=str(request.get("method", "GET")),
    )
    with urlopen(http_request, timeout=int(request.get("timeout", 30))) as response:
        return {
            "body": response.read(),
            "headers": dict(response.headers.items()),
            "status": response.status,
        }


def _transport_for(config: dict[str, Any], context: WorkflowContext) -> DownloadTransport:
    transport = config.get("transport")
    if callable(transport):
        return transport
    runtime_config = context.runtime_config or {}
    runtime_transport = runtime_config.get("download_transport")
    if callable(runtime_transport):
        return runtime_transport
    if config.get("allow_network") is True or runtime_config.get("allow_network_downloads") is True:
        return _default_transport
    raise RuntimeError("Download requires an injected transport or allow_network_downloads=True")


def download_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Download tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    url_field = str(config.get("url_field", ""))
    if not url_field:
        raise ValueError("Download config requires url_field")
    if str(config.get("output_mode", "String")).lower() != "string":
        raise NotImplementedError("Download currently supports only String output mode")
    ensure_fields_exist(input_frame, [url_field])

    transport = _transport_for(config, context)
    headers = _configured_headers(config)
    payload = config.get("payload") if isinstance(config.get("payload"), dict) else {}
    method = str(payload.get("http_action", "GET") or "GET").upper()
    timeout = int(config.get("timeout", 30) or 30)

    output_rows: list[dict[str, Any]] = []
    for row in input_frame.to_dict("records"):
        url = _encode_url_if_requested(str(row[url_field]), config)
        request = {
            "method": method,
            "url": url,
            "headers": headers,
            "body": _payload_body(row, config),
            "timeout": timeout,
        }
        response = transport(request)
        output_row = dict(row)
        output_row["DownloadData"] = _response_body(response.get("body"))
        output_row["DownloadHeaders"] = _response_headers(response.get("headers"))
        output_rows.append(output_row)

    output = pd.DataFrame(output_rows, columns=[*input_frame.columns, "DownloadData", "DownloadHeaders"])
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Download",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "url_field": url_field,
            "output_mode": config.get("output_mode", "String"),
            "headers": headers,
            "payload": payload,
            "timeout": timeout,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class DownloadTool(BaseTool):
    tool_type = "Download"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return download_tool(inputs, config, context)
