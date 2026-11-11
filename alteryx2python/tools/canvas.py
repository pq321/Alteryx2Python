from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _record_canvas_node(
    *,
    tool_type: str,
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    outputs: dict[str, pd.DataFrame] = {}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=tool_type,
        source_tool_id=config.get("source_tool_id"),
        inputs=inputs,
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "input_schemas": {
                anchor: snapshot_schema(frame)
                for anchor, frame in inputs.items()
                if isinstance(frame, pd.DataFrame)
            },
        },
    )
    return outputs


def textbox_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _record_canvas_node(tool_type="TextBox", inputs=inputs, config=config, context=context)


def htmlbox_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _record_canvas_node(tool_type="HtmlBox", inputs=inputs, config=config, context=context)


def toolcontainer_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _record_canvas_node(tool_type="ToolContainer", inputs=inputs, config=config, context=context)


def controlcontainer_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if 'Log' not in config.get('node_output_anchors', []):
        return _record_canvas_node(tool_type="ControlContainer", inputs=inputs, config=config, context=context)
    active = not config.get('disabled', False) and ('Control' not in inputs or len(inputs['Control'].index) > 0)
    outputs = {'Log': pd.DataFrame({'Message': [config.get('caption', 'Container completed')]} if active else {'Message': []})}
    context.record_node(node_id=str(config.get('node_id', 'unknown')), tool_type='ControlContainer',
                        source_tool_id=config.get('source_tool_id'), inputs=inputs, outputs=outputs, status='success', config=config)
    return outputs


def browsev2_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _record_canvas_node(tool_type="BrowseV2", inputs=inputs, config=config, context=context)


def message_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _record_canvas_node(tool_type="Message", inputs=inputs, config=config, context=context)


class TextBoxTool(BaseTool):
    tool_type = "TextBox"
    input_anchors = ()
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return textbox_tool(inputs, config, context)


class HtmlBoxTool(BaseTool):
    tool_type = "HtmlBox"
    input_anchors = ()
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return htmlbox_tool(inputs, config, context)


class ToolContainerTool(BaseTool):
    tool_type = "ToolContainer"
    input_anchors = ()
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return toolcontainer_tool(inputs, config, context)


class ControlContainerTool(BaseTool):
    tool_type = "ControlContainer"
    input_anchors = ()
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return controlcontainer_tool(inputs, config, context)


class BrowseV2Tool(BaseTool):
    tool_type = "BrowseV2"
    input_anchors = ("Input",)
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return browsev2_tool(inputs, config, context)


class MessageTool(BaseTool):
    tool_type = "Message"
    input_anchors = ("Input",)
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return message_tool(inputs, config, context)
