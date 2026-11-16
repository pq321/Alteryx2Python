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


def control_log_frame(node_id: str, active: bool, messages=()) -> pd.DataFrame:
    rows = []
    if active:
        rows.append((int(node_id), "Info", "Control Container Activated."))
        rows.extend(
            (int(entry["node_id"]), "Warning" if entry["severity"] == "warning" else "Info", entry["message"])
            for entry in messages
        )
        rows.append((int(node_id), "Info", "Control Container Completed."))
    log = pd.DataFrame(rows, columns=["ToolID", "MessageType", "Message"]).astype(
        {"ToolID": "int32", "MessageType": object, "Message": object}
    )
    log.attrs["alteryx_schema"] = [
        {"name": "ToolID", "type": "Int32", "size": None, "scale": None},
        *({"name": name, "type": "V_WString", "size": "64000", "scale": None}
          for name in ("MessageType", "Message")),
    ]
    return log


def controlcontainer_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if 'Log' not in config.get('node_output_anchors', []):
        return _record_canvas_node(tool_type="ControlContainer", inputs=inputs, config=config, context=context)
    node_id = str(config.get("node_id", "0"))
    active = not config.get("disabled", False) and ("Control" not in inputs or not inputs["Control"].empty)
    outputs = {"Log": control_log_frame(node_id, active, config.get("control_log_messages", ()))}
    context.record_node(node_id=node_id, tool_type='ControlContainer',
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
    from alteryx2python.expressions.evaluator import evaluate_expression
    from alteryx2python.expressions.parser import parse_expression

    frame = inputs["Input"]
    when = (config.get("when") or "First").lower()
    if when == "first":
        candidates = frame.head(1).to_dict("records") or [{}]
    elif when == "last":
        candidates = frame.tail(1).to_dict("records") or [{}]
    elif when == "filter":
        predicate = parse_expression(config["filter"])
        candidates = [
            row for row in frame.to_dict("records") if evaluate_expression(predicate, row)
        ]
    elif when == "all":
        candidates = [{}]
    else:
        raise NotImplementedError(f"Unsupported Message timing: {when}")
    severity = (config.get("type") or "Message").lower()
    if severity not in {"message", "warning", "error"}:
        raise NotImplementedError(f"Unsupported Message type: {severity}")
    expression = parse_expression(config["message_expression"])

    def emit():
        for row in candidates:
            message = str(evaluate_expression(expression, row))
            if severity == "error":
                context.record_error(message)
                raise ValueError(message)
            if severity == "warning":
                context.record_warning(message)
            context.record_diagnostic({
                "kind": "message",
                "node_id": str(config.get("node_id", "unknown")),
                "severity": severity,
                "message": message,
            })

    if when == "all":
        context.deferred_messages.append((str(config.get("node_id", "unknown")), emit))
    else:
        emit()
    outputs = {"Output": frame.copy()}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Message",
        source_tool_id=config.get("source_tool_id"),
        inputs=inputs,
        outputs=outputs,
        status="success",
        config=config,
    )
    return outputs


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
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return message_tool(inputs, config, context)
