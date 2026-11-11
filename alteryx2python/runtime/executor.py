from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

import pandas as pd

from alteryx2python.contracts import validate_node_contract
from alteryx2python.diagnostics import build_node_failure_diagnostic, build_routing_failure_diagnostic
from alteryx2python.runtime.node_result import NodeResult, WorkflowGraphResult
from alteryx2python.tools.registry import TOOL_REGISTRY

if TYPE_CHECKING:
    from alteryx2python.ir.models import EdgeIR, NodeIR, WorkflowIR
    from alteryx2python.runtime.context import WorkflowContext
    from alteryx2python.tools.registry import ToolMetadata


def run_tool_node(
    metadata: "ToolMetadata",
    inputs: dict[str, pd.DataFrame],
    config: dict[str, object],
    context: "WorkflowContext",
    expected_output_schema: dict[str, object] | None = None,
) -> NodeResult:
    outputs = metadata.function(inputs, config, context)
    trace = context.traces[-1] if context.traces else None
    node_id = str(config.get("node_id", "unknown"))
    contract_evidence = validate_node_contract(
        node_id=node_id,
        tool_type=metadata.tool_type,
        declared_output_anchors=metadata.output_anchors,
        inputs=inputs,
        outputs=outputs,
        config=config,
        expected_output_schema=expected_output_schema,
    )
    return NodeResult(
        node_id=node_id,
        tool_type=metadata.tool_type,
        outputs=outputs,
        trace=trace,
        contract_evidence=contract_evidence,
    )


def run_workflow_graph(
    workflow: "WorkflowIR",
    context: "WorkflowContext",
    initial_inputs: dict[str, dict[str, pd.DataFrame]] | None = None,
    target_node_ids: set[str] | None = None,
) -> WorkflowGraphResult:
    from alteryx2python.workflow_events import workflow_events, run_events
    from alteryx2python.engine_variables import resolve_workflow_tokens
    from pathlib import Path
    _answers = (context.runtime_config or {}).get("answers") or {}
    if _answers or getattr(workflow, "source_xml", ""):
        resolve_workflow_tokens(workflow, _answers)
    events = workflow_events(workflow.source_xml)
    if events:
        context.runtime_config = {'workflow_dir': str(Path(workflow.source_file).resolve().parent),
                                  **(context.runtime_config or {})}
    if not events:
        return _run_workflow_graph(workflow, context, initial_inputs, target_node_ids)
    import warnings
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter('always', RuntimeWarning)
        try:
            run_events(events, 'before', context)
            result = _run_workflow_graph(workflow, context, initial_inputs, target_node_ids)
        except Exception:
            for warning in emitted:
                context.record_warning(str(warning.message))
            run_events(events, 'failure', context)
            raise
        for warning in emitted:
            context.record_warning(str(warning.message))
    run_events(events, 'success', context)
    return result


def _run_workflow_graph(
    workflow: "WorkflowIR",
    context: "WorkflowContext",
    initial_inputs: dict[str, dict[str, pd.DataFrame]] | None = None,
    target_node_ids: set[str] | None = None,
) -> WorkflowGraphResult:
    if workflow.metadata.get("embedded_macros"):
        context.runtime_config = {**(context.runtime_config or {}), "_embedded_macros": workflow.metadata["embedded_macros"]}
    if workflow.source_xml and not workflow.metadata.get("configuration_applied"):
        runtime_config = context.runtime_config or {}
        if not runtime_config.get("skip_app_configuration"):
            from xml.etree import ElementTree as ET
            root = ET.fromstring(workflow.source_xml)
            if root.find("./Properties/RuntimeProperties/Questions") is not None or root.find("./Properties/RuntimeProperties/Actions") is not None:
                from alteryx2python.runtime.app_config import prepare_workflow
                workflow = prepare_workflow(workflow, runtime_config.get("answers"))
                context.record_diagnostic({"kind": "configuration", "source_sha256": workflow.source_hash,
                                           "bound_questions": list(workflow.metadata.get("answers", {}))})
    from alteryx2python.generator.macro_sources import attach_macro_ordering
    attach_macro_ordering(workflow, (context.runtime_config or {}).get('_embedded_macros', {}))
    nodes_by_id = {node.node_id: node for node in workflow.nodes}
    incoming_edges = _incoming_edges_by_target(workflow.edges)
    outgoing_edges = _outgoing_edges_by_source(workflow.edges)
    executable_node_ids = _target_ancestor_node_ids(workflow, target_node_ids)
    executable_nodes = [node for node in workflow.nodes if node.node_id in executable_node_ids]
    executable_edges = [
        edge
        for edge in workflow.edges
        if edge.source_node_id in executable_node_ids and edge.target_node_id in executable_node_ids
    ]
    execution_order = _topological_order(executable_nodes, executable_edges)

    initial_inputs = initial_inputs or {}
    node_results: dict[str, NodeResult] = {}

    for node_id in execution_order:
        node = nodes_by_id[node_id]
        inputs = dict(initial_inputs.get(node_id, {}))
        input_connection_names: dict[str, str] = {}
        for edge in incoming_edges.get(node_id, []):
            upstream = node_results.get(edge.source_node_id)
            if upstream is None:
                exc = KeyError(f"Missing upstream result for node {edge.source_node_id}")
                config = _execution_config(node)
                _record_node_failure(workflow, context, node, inputs, config, exc)
                raise exc
            if edge.source_anchor not in upstream.outputs:
                exc = KeyError(
                    f"Missing output anchor {edge.source_anchor} from node {edge.source_node_id}"
                )
                context.record_error(str(exc))
                context.record_diagnostic(
                    build_routing_failure_diagnostic(
                        workflow=workflow,
                        node=node,
                        edge=edge,
                        exc=exc,
                        upstream_outputs=upstream.outputs,
                    )
                )
                _record_failed_trace(context, node, inputs, _execution_config(node), exc)
                raise exc
            target_anchor = _next_input_anchor_name(inputs, edge.target_anchor)
            inputs[target_anchor] = upstream.outputs[edge.source_anchor]
            connection_name = _edge_connection_name(edge)
            if connection_name:
                input_connection_names[target_anchor] = connection_name

        from alteryx2python.runtime.scheduling import container_guards
        guards = [] if target_node_ids and (context.runtime_config or {}).get('skip_app_configuration') else container_guards(node, nodes_by_id, workflow.edges)
        enabled = all(guard is not None and len(node_results[guard[0]].outputs[guard[1]].index) > 0 for guard in guards)
        if not enabled:
            metadata = _metadata_for_node(node, context)
            from alteryx2python.tools.empty_schema import skipped_frame
            frame = next(iter(inputs.values()), None)
            if node.tool_type == 'Select' and frame is not None:
                from alteryx2python.runtime.context import WorkflowContext
                outputs = metadata.function({'Input': frame.iloc[:0]}, _execution_config(node), WorkflowContext())
            else:
                outputs = {anchor: skipped_frame(node.tool_type, _execution_config(node), frame, node.expected_output_schema)
                           for anchor in metadata.output_anchors}
            context.record_node(node_id=node_id, tool_type=node.tool_type, source_tool_id=node.source_tool_id,
                                inputs=inputs, outputs=outputs, status='skipped', config={'reason': 'container_disabled_or_empty_control'})
            node_results[node_id] = NodeResult(node_id=node_id, tool_type=node.tool_type, outputs=outputs, trace=context.traces[-1])
            continue
        config = _execution_config(node)
        runtime = context.runtime_config or {}
        if runtime.get('redirect_sinks') and node.tool_type == 'DbFileOutput':
            from pathlib import Path
            file, separator, sheet = str(config['file']).partition('|||')
            config['file'] = str(Path(runtime['output_dir']) / Path(file).name) + (separator + sheet if separator else '')
        capture_dir = (context.runtime_config or {}).get("capture_output_dir")
        if capture_dir and node.tool_type == "DbFileOutput":
            from pathlib import Path
            import hashlib
            suffix = Path(str(config.get("file", "output.csv")).split("|||", 1)[0]).suffix
            identity = hashlib.sha256(workflow.source_file.encode()).hexdigest()[:12]
            config["file"] = str(Path(capture_dir) / f"python-sink-{identity}-{node.node_id}{suffix}")
        if input_connection_names:
            config["input_connection_names"] = input_connection_names
        try:
            metadata = _metadata_for_node(node, context)
            node_results[node_id] = run_tool_node(
                metadata,
                inputs,
                config,
                context,
                expected_output_schema=node.expected_output_schema,
            )
        except Exception as exc:
            _record_node_failure(workflow, context, node, inputs, config, exc)
            raise

    warnings = _record_frontier_warnings(workflow, context, executable_node_ids, outgoing_edges, nodes_by_id)
    skipped_node_ids = [node.node_id for node in workflow.nodes if node.node_id not in executable_node_ids]
    return WorkflowGraphResult(
        node_results=node_results,
        execution_order=execution_order,
        skipped_node_ids=skipped_node_ids,
        warnings=warnings,
    )


def _metadata_for_node(node: "NodeIR", context: "WorkflowContext") -> "ToolMetadata":
    if node.tool_type.startswith("Macro_"):
        from alteryx2python.tools.macro_engine import execute_static_macro
        from alteryx2python.tools.registry import ToolMetadata
        from alteryx2python.tools.base_tool import BaseTool
        from pathlib import Path
        from xml.etree import ElementTree as ET
        cfg = _execution_config(node)
        macro_path = Path(str(cfg.get("macro_path", "")))
        candidates = [macro_path] if macro_path.is_absolute() else [Path(str(cfg.get("base_dir", "."))) / macro_path, Path("D:/Alteryx/bin/RuntimeData/Macros") / macro_path]
        embedded = (context.runtime_config or {}).get("_embedded_macros", {})
        available = next((p.resolve() for p in candidates if p.is_file() or str(p.resolve()) in embedded), None)
        declared_outputs = tuple(anchor.name for anchor in node.output_anchors)
        if available is not None:
            root = ET.fromstring(embedded[str(available)]) if str(available) in embedded else ET.parse(available).getroot()
            loop = root.findtext("./Properties/RuntimeProperties/IterativeMacro/Output")
            declared_outputs = tuple(element.findtext("Properties/Configuration/Name", "Output")
                                     for element in root.iter("Node")
                                     if "MacroOutput" in (element.find("GuiSettings").get("Plugin", "") if element.find("GuiSettings") is not None else "")
                                     and element.findtext("Properties/Configuration/Name", "Output") != loop)
        return ToolMetadata(tool_type=node.tool_type, function=execute_static_macro, tool_class=BaseTool,
                            input_anchors=tuple(anchor.name for anchor in node.input_anchors),
                            output_anchors=declared_outputs or ("Output",),
                            maturity="L2_BASIC_IMPLEMENTATION", semantics_doc="docs/tools/static_macros.md",
                            supports_certification=False, execution_profile="local-static-macro")
    try:
        metadata = TOOL_REGISTRY.get(node.tool_type)
        if node.tool_type == 'ControlContainer' and any(anchor.name == 'Log' for anchor in node.output_anchors):
            from dataclasses import replace
            metadata = replace(metadata, output_anchors=('Log',))
        return metadata
    except KeyError as exc:
        message = f"Unsupported workflow tool: {node.tool_type} (node {node.node_id})"
        context.record_error(message)
        raise NotImplementedError(message) from exc


def _execution_config(node: "NodeIR") -> dict[str, object]:
    normalized = node.config.get("normalized", node.config)
    if not isinstance(normalized, dict):
        normalized = {}
    return {
        **normalized,
        "node_id": node.node_id,
        "source_tool_id": node.source_tool_id,
        "node_input_anchors": [anchor.name for anchor in node.input_anchors],
        "node_output_anchors": [anchor.name for anchor in node.output_anchors],
        "expected_output_schema": node.expected_output_schema,
    }


def _record_node_failure(
    workflow: "WorkflowIR",
    context: "WorkflowContext",
    node: "NodeIR",
    inputs: dict[str, pd.DataFrame],
    config: dict[str, object],
    exc: Exception,
) -> None:
    if str(exc) and str(exc) not in context.errors:
        context.record_error(str(exc))
    context.record_diagnostic(
        build_node_failure_diagnostic(
            workflow=workflow,
            node=node,
            exc=exc,
            inputs=inputs,
            config=config,
        )
    )
    _record_failed_trace(context, node, inputs, config, exc)


def _record_failed_trace(
    context: "WorkflowContext",
    node: "NodeIR",
    inputs: dict[str, pd.DataFrame],
    config: dict[str, object],
    exc: Exception,
) -> None:
    context.record_node(
        node_id=node.node_id,
        tool_type=node.tool_type,
        source_tool_id=node.source_tool_id,
        inputs=inputs,
        outputs={},
        status="failed",
        config={
            **config,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
    )


def _next_input_anchor_name(inputs: dict[str, pd.DataFrame], target_anchor: str) -> str:
    if target_anchor not in inputs:
        return target_anchor
    index = 2
    while f"{target_anchor}_{index}" in inputs:
        index += 1
    return f"{target_anchor}_{index}"


def _incoming_edges_by_target(edges: list["EdgeIR"]) -> dict[str, list["EdgeIR"]]:
    incoming: dict[str, list["EdgeIR"]] = defaultdict(list)
    for edge in edges:
        incoming[edge.target_node_id].append(edge)
    return incoming


def _outgoing_edges_by_source(edges: list["EdgeIR"]) -> dict[str, list["EdgeIR"]]:
    outgoing: dict[str, list["EdgeIR"]] = defaultdict(list)
    for edge in edges:
        outgoing[edge.source_node_id].append(edge)
    return outgoing


def _edge_connection_name(edge: "EdgeIR") -> str:
    raw = edge.metadata.get("raw") if isinstance(edge.metadata, dict) else None
    if not isinstance(raw, dict):
        return ""
    attributes = raw.get("attributes")
    if not isinstance(attributes, dict):
        return ""
    return str(attributes.get("name", "") or "")


def _target_ancestor_node_ids(workflow: "WorkflowIR", target_node_ids: set[str] | None) -> set[str]:
    if target_node_ids is None:
        return {node.node_id for node in workflow.nodes}

    node_ids = {node.node_id for node in workflow.nodes}
    unknown_targets = sorted(target_node_ids - node_ids)
    if unknown_targets:
        raise ValueError(f"Target nodes are not present in workflow: {', '.join(unknown_targets)}")

    from alteryx2python.runtime.scheduling import scheduling_dependencies
    incoming = {}
    for source, target in scheduling_dependencies(workflow.nodes, workflow.edges):
        incoming.setdefault(target, []).append(source)
    selected: set[str] = set()
    queue = deque(target_node_ids)
    while queue:
        node_id = queue.popleft()
        if node_id in selected:
            continue
        selected.add(node_id)
        for source in incoming.get(node_id, []):
            queue.append(source)
    return selected


def _record_frontier_warnings(
    workflow: "WorkflowIR",
    context: "WorkflowContext",
    executable_node_ids: set[str],
    outgoing_edges: dict[str, list["EdgeIR"]],
    nodes_by_id: dict[str, "NodeIR"],
) -> list[str]:
    if len(executable_node_ids) == len(workflow.nodes):
        return []
    warnings: list[str] = []
    for node_id in sorted(executable_node_ids, key=lambda item: int(item) if item.isdigit() else item):
        for edge in outgoing_edges.get(node_id, []):
            if edge.target_node_id in executable_node_ids:
                continue
            target = nodes_by_id[edge.target_node_id]
            message = (
                f"Skipped frontier node {target.node_id} ({target.tool_type}) "
                f"downstream of {node_id}:{edge.source_anchor}"
            )
            warnings.append(message)
            context.record_warning(message)
    return warnings


def _topological_order(nodes: list["NodeIR"], edges: list["EdgeIR"]) -> list[str]:
    from alteryx2python.runtime.scheduling import scheduling_dependencies
    node_ids = [node.node_id for node in nodes]
    node_id_set = set(node_ids)
    indegree = {node_id: 0 for node_id in node_ids}
    outgoing = {}

    pairs = scheduling_dependencies(nodes, edges)
    positions = {node_id: index for index, node_id in enumerate(node_ids)}
    ordered_pairs = list(dict.fromkeys((edge.source_node_id, edge.target_node_id) for edge in edges))
    ordered_pairs.extend(sorted(pairs - set(ordered_pairs), key=lambda pair: (positions.get(pair[0], -1), positions.get(pair[1], -1))))
    for source, target in ordered_pairs:
        if source not in node_id_set or target not in node_id_set:
            raise ValueError(f"Workflow edge references unknown node: {source} -> {target}")
        indegree[target] += 1
        outgoing.setdefault(source, []).append(target)

    queue = deque(node_id for node_id in node_ids if indegree[node_id] == 0)
    order: list[str] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for target in outgoing.get(node_id, []):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(order) != len(nodes):
        raise ValueError("Workflow graph contains a cycle")
    return order
