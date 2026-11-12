"""Execution of ordinary local, static user macros through the canonical graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.unavailable import ToolUnavailableError


def macro_output(
    inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("MacroOutput requires Input")
    outputs = {"Output": inputs["Input"].copy()}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        source_tool_id=config.get("source_tool_id"),
        tool_type="MacroOutput",
        inputs=inputs,
        outputs=outputs,
        status="success",
        config=config,
    )
    return outputs


def macro_boundary_input(
    inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("Macro boundary has no bound Input")
    outputs = {"Output": inputs["Input"].copy()}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        source_tool_id=config.get("source_tool_id"),
        tool_type="MacroBoundaryInput",
        inputs=inputs,
        outputs=outputs,
        status="success",
        config=config,
    )
    return outputs


def execute_static_macro(
    inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext
) -> dict[str, pd.DataFrame]:
    from alteryx2python.parser.xml_parser import XmlWorkflowParser
    from alteryx2python.runtime.executor import run_workflow_graph

    raw_path = str(config.get("macro_path", ""))
    if not raw_path:
        raise ToolUnavailableError(
            "Macro path was not preserved in the parsed workflow"
        )
    path = Path(raw_path)
    roots = [
        Path(str(config.get("base_dir", "."))),
        Path("D:/Alteryx/bin/RuntimeData/Macros"),
    ]
    candidates = [path] if path.is_absolute() else [root / path for root in roots]
    embedded = (context.runtime_config or {}).get("_embedded_macros", {})
    path = next(
        (
            candidate.resolve()
            for candidate in candidates
            if candidate.is_file() or str(candidate.resolve()) in embedded
        ),
        None,
    )
    if path is None:
        raise ToolUnavailableError(f"Local macro file is unavailable: {raw_path}")
    stack = list((context.runtime_config or {}).get("macro_stack", []))
    if str(path) in stack:
        raise ToolUnavailableError(
            "Recursive/iterative macros require an iteration adapter"
        )
    root = (
        ET.fromstring(embedded[str(path)])
        if str(path) in embedded
        else ET.parse(path).getroot()
    )
    from alteryx2python.runtime.app_config import prepare_workflow, question_manifest
    from alteryx2python.parser.tool_parsers.common import as_list

    # Macro callers serialize question answers as <Value name="...">...</Value>.
    values = config.get("macro_answers", {})
    values = dict(values)
    for item in as_list(config.get("Value", [])):
        if isinstance(item, dict):
            attrs = item.get("attributes", item.get("@attributes", {}))
            name = attrs.get("name", item.get("@name"))
            if name:
                values[name] = item.get("text", item.get("#text", ""))
    runtime_props = root.find("./Properties/RuntimeProperties")
    batch = runtime_props.find("BatchMacro") if runtime_props is not None else None
    iterative = (
        runtime_props.find("IterativeMacro") if runtime_props is not None else None
    )
    names = {}
    for element in root.iter("Node"):
        cfg = element.find("Properties/Configuration")
        names[element.get("ToolID")] = (
            cfg.findtext("Name", "") if cfg is not None else ""
        )
    runs = []

    def once(bound_inputs, answers):
        macro = prepare_workflow(
            XmlWorkflowParser().parse_xml(embedded[str(path)], path)
            if str(path) in embedded
            else XmlWorkflowParser().parse(path),
            answers,
        )
        initial, outputs, active_nodes = {}, {}, []
        boundaries = [node for node in macro.nodes if node.tool_type == "MacroInput"]
        for node in macro.nodes:
            entry = node.metadata.get("catalog", {})
            if (entry.get("gui_only") and node.tool_type not in {'ToolContainer','ControlContainer'}) or node.tool_type in {
                "TextBox",
                "HtmlBox",
            }:
                continue
            if node.tool_type == "MacroInput":
                name = names.get(node.node_id) or "Input"
                bound = bound_inputs.get(name)
                if bound is None and len(boundaries) == 1 and len(bound_inputs) == 1:
                    bound = next(iter(bound_inputs.values()))
                if bound is None:
                    raise KeyError(f"Macro input is missing: {name}")
                node.tool_type = "MacroBoundaryInput"
                initial[node.node_id] = {"Input": bound}
            if node.tool_type == "MacroOutput":
                outputs[node.node_id] = names.get(node.node_id) or "Output"
            active_nodes.append(node)
        active_ids = {node.node_id for node in active_nodes}
        macro.nodes = active_nodes
        macro.edges = [
            edge
            for edge in macro.edges
            if edge.source_node_id in active_ids and edge.target_node_id in active_ids
        ]
        child_runtime = dict(context.runtime_config or {})
        child_runtime.pop('constants', None)
        child = WorkflowContext(
            runtime_config={
                **child_runtime,
                "macro_stack": [*stack, str(path)],
            }
        )
        result = run_workflow_graph(macro, child, initial_inputs=initial)
        context.warnings.extend(child.warnings)
        context.errors.extend(child.errors)
        runs.append(result.execution_order)
        mapped = {
            name: result.node_results[node_id].outputs["Output"]
            for node_id, name in outputs.items()
        }
        if not mapped:
            raise ValueError("Macro has no MacroOutput boundary")
        return mapped

    if batch is not None and iterative is not None:
        raise ToolUnavailableError("Combined batch/iterative macro mode is unsupported")
    if batch is not None:
        controls = [q for q in question_manifest(root) if q.kind == "ControlParam"]
        if len(controls) != 1:
            raise ToolUnavailableError(
                "Local batch profile requires exactly one ControlParam"
            )
        control = controls[0]
        control_anchor = config.get("control_anchor", control.name)
        control_frame = inputs.get(control_anchor)
        if control_frame is None:
            raise KeyError(f"Batch macro control input is missing: {control_anchor}")
        field = config.get("control_field", values.get(control.name))
        if field is None and len(control_frame.columns) == 1:
            field = control_frame.columns[0]
        if field not in control_frame:
            raise ValueError("Batch macro requires a valid control_field")
        data = {key: value for key, value in inputs.items() if key != control_anchor}
        collected = {}
        for value in control_frame[field]:
            result = once(data, {**values, control.name: value})
            for name, frame in result.items():
                collected.setdefault(name, []).append(frame)
        if not collected:
            for element in root.iter("Node"):
                gui = element.find("GuiSettings")
                if gui is None or "MacroOutput" not in gui.get("Plugin", ""):
                    continue
                fields = element.findall("Properties/MetaInfo/RecordInfo/Field")
                if not fields:
                    raise ToolUnavailableError(
                        "Empty batch control needs an independently declared output schema"
                    )
                name = element.findtext("Properties/Configuration/Name", "Output")
                frame = pd.DataFrame(columns=[field.get("name") for field in fields])
                frame.attrs["alteryx_schema"] = [dict(field.attrib) for field in fields]
                collected[name] = [frame]
            if not collected:
                raise ToolUnavailableError(
                    "Empty batch has no declared output boundaries"
                )
        mode = batch.findtext("OutputMode", "AllSame")
        if mode not in {"AllSame", "AutoByName", "AutoByPosition"}:
            raise ToolUnavailableError(f"Unsupported batch output mode: {mode}")
        mapped = {}
        for name, frames in collected.items():
            if mode == "AllSame" and any(
                list(f.columns) != list(frames[0].columns) for f in frames
            ):
                raise ValueError("Batch AllSame outputs have different field layouts")
            if mode == "AutoByPosition":
                if any(len(f.columns) != len(frames[0].columns) for f in frames):
                    raise ValueError(
                        "Batch position outputs have different column counts"
                    )
                frames = [f.set_axis(frames[0].columns, axis=1) for f in frames]
            mapped[name] = pd.concat(frames, ignore_index=True, sort=False)
    elif iterative is not None:
        input_name, output_name = (
            iterative.findtext("Input"),
            iterative.findtext("Output"),
        )
        limit_node = iterative.find("IterationLimit")
        limit = int(limit_node.get("value", "100")) if limit_node is not None else 100
        budget = int((context.runtime_config or {}).get("macro_max_iterations", 1000))
        if limit < 1 or limit > budget:
            raise ToolUnavailableError(
                "Macro iteration limit exceeds configured local budget"
            )
        data, collected = dict(inputs), {}
        for index in range(limit):
            result = once(data, values)
            if output_name not in result:
                raise ValueError("Iterative macro loop output does not exist")
            for name, frame in result.items():
                if name != output_name:
                    collected.setdefault(name, []).append(frame)
            if result[output_name].empty:
                break
            data[input_name] = result[output_name]
        else:
            if iterative.findtext("LimitBehavior", "Error") != "Ignore":
                raise ValueError("Iterative macro iteration limit reached")
        mapped = {
            name: pd.concat(frames, ignore_index=True, sort=False)
            for name, frames in collected.items()
        }
    else:
        mapped = once(inputs, values)
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        source_tool_id=config.get("source_tool_id"),
        tool_type=str(config.get("macro_tool_type", f"Macro_{path.stem}")),
        inputs=inputs,
        outputs=mapped,
        status="success",
        config={
            "macro_path": str(path),
            "child_execution_orders": runs,
        },
    )
    return mapped


IMPLEMENTATIONS = {
    "MacroOutput": macro_output,
    "MacroBoundaryInput": macro_boundary_input,
}
ANCHORS = {name: (("Input",), ("Output",)) for name in IMPLEMENTATIONS}
PARSERS = {}
