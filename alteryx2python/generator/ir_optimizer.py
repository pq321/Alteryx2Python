"""Phase 2 IR graph optimization and redundancy elimination passes.

Phase 1 preserves exact 1-to-1 Alteryx node topology for Designer parity. Once
Phase 1 parity is established, Phase 2 optimizes WorkflowIR before emitting
native Python:
  1. Classify macros: inline 1-call standard macros, deduplicate multi-call
     standard macros into reusable subgraphs, and extract Batch/Iterative loop specs.
  2. Fold private 1-row parameter TextInput + AppendFields patterns into scalar
     workflow parameters in general dynamic mode.
  3. Eliminate non-functional UI nodes, passthrough wrappers, identity Selects,
     and unreachable dead branches.
  4. Algebraically fuse consecutive Select chains, Formula chains, and
     single-branch Filter chains, and prune provably dead intermediate columns.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass, replace
from pathlib import Path
import re
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd

from alteryx2python.expressions.ast import (
    BinaryExpression,
    ConditionalExpression,
    ExpressionNode,
    FieldReference,
    FunctionExpression,
    LiteralExpression,
    UnaryExpression,
)
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.generator.macro_sources import ordered_macro_outputs, resolve_macro_path
from alteryx2python.generator.parameters import ParameterExpression, prepare_parameters
from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR, WorkflowIR


UI_NOOP_TOOLS = frozenset({"BrowseV2", "TextBox", "HtmlBox"})
OBSERVABLE_SINK_TOOLS = frozenset({
    "DbFileOutput",
    "PortfolioComposerRender",
    "Email",
    "RunCommand",
    "Message",
    "MacroOutput",
})


@dataclass
class MacroSubgraphSpec:
    """A standard macro invoked multiple times and lowered once as a shared function."""

    macro_key: str
    macro_path: str
    workflow: WorkflowIR
    input_anchors: list[str]
    output_anchors: list[str]
    parameters: list[dict[str, Any]] = field(default_factory=list)
    parameter_expressions: dict[tuple[str, tuple[Any, ...]], ExpressionNode] = field(default_factory=dict)


@dataclass
class LoopMacroSpec:
    """A Batch or Iterative macro lowered to an explicit native Python loop."""

    macro_key: str
    macro_path: str
    kind: str  # "batch" | "iterative"
    workflow: WorkflowIR
    input_anchors: list[str]
    output_anchors: list[str]
    parameters: list[dict[str, Any]] = field(default_factory=list)
    parameter_expressions: dict[tuple[str, tuple[Any, ...]], ExpressionNode] = field(default_factory=dict)
    control_param: str | None = None
    control_anchor: str | None = None
    output_mode: str = "AllSame"
    output_columns: dict[str, list[str]] = field(default_factory=dict)
    iteration_input: str | None = None
    iteration_output: str | None = None
    iteration_limit: int = 100
    limit_behavior: str = "Error"


@dataclass
class OptimizationResult:
    """Optimized IR plus extracted macro/parameter metadata and node provenance."""

    workflow: WorkflowIR
    parameters: list[dict[str, Any]] = field(default_factory=list)
    parameter_bindings: list[dict[str, Any]] = field(default_factory=list)
    parameter_expressions: dict[tuple[str, tuple[Any, ...]], ExpressionNode] = field(default_factory=dict)
    reusable_macros: dict[str, MacroSubgraphSpec] = field(default_factory=dict)
    loop_macros: dict[str, LoopMacroSpec] = field(default_factory=dict)
    provenance: dict[str, dict[str, Any]] = field(default_factory=dict)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value)).strip("_").lower()
    return cleaned or "macro"


def _norm_cfg(node: NodeIR) -> dict[str, Any]:
    return node.config.get("normalized", node.config)


def _set_norm_cfg(node: NodeIR, updated: dict[str, Any]) -> None:
    if "normalized" in node.config and isinstance(node.config["normalized"], dict):
        node.config["normalized"] = updated
    else:
        node.config = updated


def _rebuild_edge_lists(workflow: WorkflowIR) -> None:
    incoming: dict[str, list[str]] = {node.node_id: [] for node in workflow.nodes}
    outgoing: dict[str, list[str]] = {node.node_id: [] for node in workflow.nodes}
    for edge in workflow.edges:
        if edge.target_node_id in incoming:
            incoming[edge.target_node_id].append(edge.edge_id)
        if edge.source_node_id in outgoing:
            outgoing[edge.source_node_id].append(edge.edge_id)
    for node in workflow.nodes:
        node.incoming_edges = incoming[node.node_id]
        node.outgoing_edges = outgoing[node.node_id]


def _container_scope(node: NodeIR, by_id: dict[str, NodeIR]) -> tuple[str, ...]:
    chain: list[str] = []
    current = node.config.get("container_id") or _norm_cfg(node).get("container_id")
    while current and current in by_id:
        container = by_id[current]
        cfg = _norm_cfg(container)
        is_dynamic = bool(container.metadata.get("disabled_parameter"))
        is_disabled = bool(cfg.get("disabled"))
        if container.tool_type == "ControlContainer" or is_dynamic or is_disabled:
            chain.append(current)
        current = container.config.get("container_id") or cfg.get("container_id")
    return tuple(chain)


def _extract_macro_caller_answers(config: dict[str, Any]) -> dict[str, Any]:
    answers = dict(config.get("macro_answers", {}))
    values = config.get("Value", [])
    for item in values if isinstance(values, list) else [values]:
        if isinstance(item, dict):
            attrs = item.get("attributes", item.get("@attributes", {}))
            name = attrs.get("name", item.get("@name"))
            if name:
                answers[name] = item.get("text", item.get("#text", ""))
    return answers


def _expression_to_alteryx(expr: ExpressionNode, param_tokens: dict[str, str] | None = None) -> str:
    """Serialize an ExpressionNode back to valid Alteryx expression syntax."""
    if isinstance(expr, ParameterExpression):
        token = (param_tokens or {}).get(expr.name, f"Question.{expr.name}")
        return f"[{token}]"
    if isinstance(expr, LiteralExpression):
        val = expr.value
        if val is None:
            return "Null()"
        if isinstance(val, bool):
            return "True" if val else "False"
        if isinstance(val, (int, float)):
            return repr(val)
        escaped = str(val).replace('"', '""')
        return f'"{escaped}"'
    if isinstance(expr, FieldReference):
        return f"[{expr.name}]"
    if isinstance(expr, UnaryExpression):
        return f"{expr.operator}({_expression_to_alteryx(expr.operand, param_tokens)})"
    if isinstance(expr, BinaryExpression):
        left = _expression_to_alteryx(expr.left, param_tokens)
        right = _expression_to_alteryx(expr.right, param_tokens)
        return f"({left} {expr.operator} {right})"
    if isinstance(expr, ConditionalExpression):
        cond = _expression_to_alteryx(expr.condition, param_tokens)
        t_val = _expression_to_alteryx(expr.true_value, param_tokens)
        f_val = _expression_to_alteryx(expr.false_value, param_tokens)
        return f"IF {cond} THEN {t_val} ELSE {f_val} ENDIF"
    if isinstance(expr, FunctionExpression):
        args = ", ".join(_expression_to_alteryx(arg, param_tokens) for arg in expr.args)
        return f"{expr.name}({args})"
    raise UnsupportedLowering(f"Cannot serialize expression node: {type(expr).__name__}")


def _rewrite_field_refs(
    expr: ExpressionNode,
    mapping: dict[str, ExpressionNode],
) -> tuple[ExpressionNode, bool]:
    """Replace matching case-insensitive FieldReferences with target ExpressionNodes."""
    lowered = {key.casefold(): val for key, val in mapping.items()}
    changed = False

    def visit(node: ExpressionNode) -> ExpressionNode:
        nonlocal changed
        if isinstance(node, FieldReference):
            replacement = lowered.get(node.name.casefold())
            if replacement is not None:
                changed = True
                return replacement
            return node
        if is_dataclass(node):
            updates: dict[str, Any] = {}
            for f in fields(node):
                val = getattr(node, f.name)
                if isinstance(val, ExpressionNode):
                    updates[f.name] = visit(val)
                elif isinstance(val, list):
                    updates[f.name] = [visit(item) if isinstance(item, ExpressionNode) else item for item in val]
            return replace(node, **updates) if updates else node
        return node

    return visit(expr), changed


def _referenced_fields(expr: ExpressionNode) -> set[str]:
    found: set[str] = set()

    def visit(node: ExpressionNode) -> None:
        if isinstance(node, FieldReference):
            raw = node.name.strip("%")
            if not raw.startswith(("Question.", "User.", "Engine.")):
                matched = re.fullmatch(r"Row-?\d+:(.+)", node.name)
                found.add(matched.group(1) if matched else node.name)
            return
        if is_dataclass(node):
            for f in fields(node):
                val = getattr(node, f.name)
                if isinstance(val, ExpressionNode):
                    visit(val)
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, ExpressionNode):
                            visit(item)

    visit(expr)
    return found


def _known_output_columns(node: NodeIR, by_id: dict[str, NodeIR], incoming_edges: dict[str, list[EdgeIR]]) -> set[str] | None:
    """Return exact output column names when statically closed, else None."""
    cfg = _norm_cfg(node)
    if node.tool_type == "TextInput":
        cols = [str(f) for f in cfg.get("fields", [])]
        return set(cols) if cols else None
    if node.tool_type == "Select":
        select_fields = cfg.get("select_fields", [])
        if not select_fields:
            return None
        has_unknown = any(f.get("source") == "*Unknown" and f.get("selected", True) for f in select_fields)
        explicit = {str(f.get("rename") or f["source"]) for f in select_fields if f.get("selected", True) and f.get("source") != "*Unknown"}
        if not has_unknown:
            return explicit
        inc = incoming_edges.get(node.node_id, [])
        if len(inc) == 1:
            upstream = _known_output_columns(by_id[inc[0].source_node_id], by_id, incoming_edges)
            if upstream is not None:
                mentioned = {str(f["source"]) for f in select_fields if f.get("source") != "*Unknown"}
                return explicit | (upstream - mentioned)
        return None
    if node.tool_type == "Formula":
        inc = incoming_edges.get(node.node_id, [])
        if len(inc) == 1:
            upstream = _known_output_columns(by_id[inc[0].source_node_id], by_id, incoming_edges)
            if upstream is not None:
                added = {str(f["field"]) for f in cfg.get("formula_fields", []) if f.get("enabled", True) and f.get("field")}
                return upstream | added
    if node.tool_type in {"Filter", "Sort", "Sample", "Unique"}:
        inc = incoming_edges.get(node.node_id, [])
        if len(inc) == 1:
            return _known_output_columns(by_id[inc[0].source_node_id], by_id, incoming_edges)
    schema_fields = (node.expected_output_schema or {}).get("fields", [])
    if schema_fields and all(isinstance(f, dict) and f.get("name") for f in schema_fields):
        return {str(f["name"]) for f in schema_fields}
    return None


def _columns_provably_dropped_before_sinks(
    start_node_id: str,
    candidate_cols: set[str],
    workflow: WorkflowIR,
    by_id: dict[str, NodeIR],
) -> set[str]:
    """Return subset of candidate_cols guaranteed not to survive to any sink/wildcard output."""
    outgoing: dict[str, list[EdgeIR]] = {}
    for edge in workflow.edges:
        outgoing.setdefault(edge.source_node_id, []).append(edge)

    surviving: set[str] = set()
    lower_to_orig = {col.casefold(): col for col in candidate_cols}

    visited: set[tuple[str, frozenset[str]]] = set()

    def walk(node_id: str, live: frozenset[str]) -> None:
        if not live:
            return
        state = (node_id, live)
        if state in visited:
            return
        visited.add(state)
        node = by_id[node_id]
        cfg = _norm_cfg(node)
        kind = node.tool_type

        if kind == "Select":
            s_fields = cfg.get("select_fields", [])
            has_unknown = any(f.get("source") == "*Unknown" and f.get("selected", True) for f in s_fields)
            explicit_map = {str(f["source"]).casefold(): f for f in s_fields if f.get("source") != "*Unknown"}
            next_live: set[str] = set()
            for col_cf in live:
                entry = explicit_map.get(col_cf)
                if entry is not None:
                    if entry.get("selected", True):
                        renamed = str(entry.get("rename") or entry["source"]).casefold()
                        if renamed != col_cf:
                            # Renamed candidate column survives under a new name -> treat as surviving
                            surviving.add(lower_to_orig[col_cf])
                        else:
                            next_live.add(col_cf)
                elif has_unknown:
                    next_live.add(col_cf)
            for edge in outgoing.get(node_id, []):
                walk(edge.target_node_id, frozenset(next_live))
            if not outgoing.get(node_id):
                for col_cf in next_live:
                    surviving.add(lower_to_orig[col_cf])
            return

        if kind == "Summarize":
            kept_sources = {str(f["field"]).casefold() for f in cfg.get("summarize_fields", [])}
            for col_cf in live & kept_sources:
                surviving.add(lower_to_orig[col_cf])
            return

        if kind in {"Formula", "Filter", "Sort", "Sample", "Unique", "RecordID"}:
            if kind == "Formula":
                overwritten = {
                    str(f["field"]).casefold()
                    for f in cfg.get("formula_fields", [])
                    if f.get("enabled", True) and f.get("field")
                }
                # If a Formula overwrites col_cf completely, downstream gets Formula's column
                next_live_f = frozenset(live - overwritten)
            else:
                next_live_f = live
            outs = outgoing.get(node_id, [])
            if not outs:
                for col_cf in next_live_f:
                    surviving.add(lower_to_orig[col_cf])
            for edge in outs:
                walk(edge.target_node_id, next_live_f)
            return

        # Conservative default for any other node (DbFileOutput, Join, Union, JupyterCode, etc.):
        for col_cf in live:
            surviving.add(lower_to_orig[col_cf])

    for edge in outgoing.get(start_node_id, []):
        walk(edge.target_node_id, frozenset(lower_to_orig.keys()))
    if not outgoing.get(start_node_id):
        return set()
    return candidate_cols - surviving


class _IROptimizer:
    def __init__(
        self,
        workflow: WorkflowIR,
        *,
        parameters: list[dict[str, Any]] | None = None,
        parameter_bindings: list[dict[str, Any]] | None = None,
        parameter_expressions: dict[tuple[str, tuple[Any, ...]], ExpressionNode] | None = None,
        macro_stack: tuple[str, ...] = (),
    ) -> None:
        from alteryx2python.runtime.app_config import prepare_workflow
        from alteryx2python.runtime.variables import bind_workflow_variables

        base = deepcopy(workflow)
        if base.source_xml and not base.metadata.get("configuration_applied"):
            base = bind_workflow_variables(prepare_workflow(base))
        elif "workflow_constants" not in base.metadata and base.source_xml:
            base = bind_workflow_variables(base)
        self.workflow = base
        self.workflow.metadata["configuration_applied"] = True
        self.parameters: list[dict[str, Any]] = deepcopy(list(parameters or []))
        self.parameter_bindings: list[dict[str, Any]] = deepcopy(
            list(parameter_bindings if parameter_bindings is not None else self.workflow.metadata.get("parameter_bindings", []))
        )
        self.parameter_expressions: dict[tuple[str, tuple[Any, ...]], ExpressionNode] = deepcopy(dict(parameter_expressions or {}))
        self.reusable_macros: dict[str, MacroSubgraphSpec] = {}
        self.loop_macros: dict[str, LoopMacroSpec] = {}
        self.provenance: dict[str, dict[str, Any]] = {
            node.node_id: {"status": "retained", "target_node_id": node.node_id, "reason": "source"}
            for node in self.workflow.nodes
        }
        self._macro_stack = macro_stack

    def _record_elimination(self, old_id: str, target_id: str | None, status: str, reason: str) -> None:
        for src_id, info in self.provenance.items():
            if src_id == old_id:
                info["status"] = status
                info["target_node_id"] = target_id
                info["reason"] = reason
            elif info.get("target_node_id") == old_id:
                info["target_node_id"] = target_id

    def run(self) -> OptimizationResult:
        self._classify_and_process_macros()
        self._fold_single_row_parameter_tables()
        for _ in range(4):
            changed = False
            changed |= self._prune_noop_and_dead_branches()
            changed |= self._fuse_select_chains()
            changed |= self._fuse_formulas()
            changed |= self._prune_dead_columns()
            if not changed:
                break
        _rebuild_edge_lists(self.workflow)
        self.workflow.metadata["parameter_bindings"] = self.parameter_bindings
        return OptimizationResult(
            workflow=self.workflow,
            parameters=self.parameters,
            parameter_bindings=self.parameter_bindings,
            parameter_expressions=self.parameter_expressions,
            reusable_macros=self.reusable_macros,
            loop_macros=self.loop_macros,
            provenance=self.provenance,
        )

    # ------------------------------------------------------------------
    # Pass 1: Macro classification, deduplication, and 1-call inlining
    # ------------------------------------------------------------------
    def _classify_and_process_macros(self) -> None:
        from alteryx2python.parser.xml_parser import XmlWorkflowParser
        from alteryx2python.runtime.app_config import prepare_workflow, question_manifest
        from alteryx2python.runtime.variables import bind_workflow_variables
        from alteryx2python.workflow_events import workflow_events

        macro_nodes = [n for n in self.workflow.nodes if n.tool_type.startswith("Macro_")]
        if not macro_nodes:
            return

        embedded = self.workflow.metadata.get("embedded_macros", {})
        resolved_by_node: dict[str, Path] = {}
        counts_by_path: dict[str, int] = {}

        for node in macro_nodes:
            cfg = _norm_cfg(node)
            raw = str(cfg.get("macro_path", ""))
            base_dir = cfg.get("base_dir") or (Path(self.workflow.source_file).parent if self.workflow.source_file else ".")
            path = resolve_macro_path(raw, base_dir, embedded)
            if path is None or str(path) in self._macro_stack:
                raise UnsupportedLowering(f"Unresolved or recursive macro: {raw}")
            resolved_by_node[node.node_id] = path
            counts_by_path[str(path)] = counts_by_path.get(str(path), 0) + 1

        reusable_key_by_path: dict[str, str] = {}
        loop_key_by_path: dict[str, str] = {}
        used_keys: set[str] = set()

        def allocate_key(stem: str) -> str:
            base = _slug(stem)
            candidate, idx = base, 1
            while candidate in used_keys:
                idx += 1
                candidate = f"{base}_{idx}"
            used_keys.add(candidate)
            return candidate

        for parent in list(macro_nodes):
            path = resolved_by_node[parent.node_id]
            xml = embedded.get(str(path)) or path.read_text(encoding="utf-8-sig")
            if workflow_events(xml):
                raise UnsupportedLowering(f"Macro-local workflow events require a dedicated template: {path.name}")
            root = ET.fromstring(xml)
            runtime_props = root.find("./Properties/RuntimeProperties")
            batch_el = runtime_props.find("BatchMacro") if runtime_props is not None else None
            iter_el = runtime_props.find("IterativeMacro") if runtime_props is not None else None
            if batch_el is not None and iter_el is not None:
                raise UnsupportedLowering(f"Combined batch/iterative macro mode is unsupported: {path.name}")

            caller_answers = _extract_macro_caller_answers(_norm_cfg(parent))
            boundary_names = {
                el.get("ToolID"): (el.findtext("Properties/Configuration/Name") or "Output")
                for el in root.iter("Node")
            }
            input_names = [
                el.findtext("Properties/Configuration/Name") or "Input"
                for el in root.iter("Node")
                if el.find("GuiSettings") is not None and "MacroInput" in el.find("GuiSettings").get("Plugin", "")
            ]
            ordered = ordered_macro_outputs(root)
            output_names = ordered or [
                el.findtext("Properties/Configuration/Name") or "Output"
                for el in root.iter("Node")
                if el.find("GuiSettings") is not None and "MacroOutput" in el.find("GuiSettings").get("Plugin", "")
            ]
            if not output_names:
                raise UnsupportedLowering(f"Macro has no output: {path.name}")

            # Case 1a: Batch or Iterative Macro -> LoopMacroSpec
            if batch_el is not None or iter_el is not None:
                kind = "batch" if batch_el is not None else "iterative"
                cache_sig = f"{path}::{kind}::{sorted((k, v) for k, v in caller_answers.items() if k != 'ControlParams')}"
                if cache_sig not in loop_key_by_path:
                    macro_key = allocate_key(path.stem)
                    parsed_child = XmlWorkflowParser().parse_xml(xml, path)
                    parsed_child.metadata["embedded_macros"] = embedded
                    if kind == "batch":
                        controls = [q for q in question_manifest(root) if q.kind == "ControlParam"]
                        if len(controls) != 1:
                            raise UnsupportedLowering(f"Batch macro requires a single ControlParam: {path.name}")
                        control_q = controls[0]
                        static_answers = {k: v for k, v in caller_answers.items() if k not in {"ControlParams", control_q.name}}
                        # Use dynamic parameter lowering for ControlParam when supported; otherwise prepare body
                        prepared_child, param_exprs, param_specs = self._prepare_macro_body(
                            parsed_child, static_answers, dynamic_questions=[control_q.name]
                        )
                        opt_child = _IROptimizer(
                            prepared_child,
                            parameters=param_specs,
                            parameter_expressions=param_exprs,
                            macro_stack=(*self._macro_stack, str(path)),
                        ).run()
                        self.reusable_macros.update(opt_child.reusable_macros)
                        self.loop_macros.update(opt_child.loop_macros)
                        output_mode = batch_el.findtext("OutputMode", "AllSame")
                        if output_mode not in {"AllSame", "AutoByName", "AutoByPosition"}:
                            raise UnsupportedLowering(f"Unsupported batch output mode: {output_mode}")
                        output_columns = {
                            el.findtext("Properties/Configuration/Name", "Output"):
                                [column.get("name") for column in el.findall("Properties/MetaInfo/RecordInfo/Field")]
                            for el in root.iter("Node")
                            if (gui := el.find("GuiSettings")) is not None and "MacroOutput" in gui.get("Plugin", "")
                        }
                        self.loop_macros[macro_key] = LoopMacroSpec(
                            macro_key=macro_key,
                            macro_path=str(path),
                            kind="batch",
                            workflow=opt_child.workflow,
                            input_anchors=input_names,
                            output_anchors=output_names,
                            parameters=opt_child.parameters,
                            parameter_expressions=opt_child.parameter_expressions,
                            control_param=control_q.name,
                            control_anchor=_norm_cfg(parent).get("control_anchor"),
                            output_mode=output_mode,
                            output_columns=output_columns,
                        )
                    else:
                        iter_in = iter_el.findtext("Input")
                        iter_out = iter_el.findtext("Output")
                        limit_node = iter_el.find("IterationLimit")
                        limit = int(limit_node.get("value", "100")) if limit_node is not None else 100
                        limit_behavior = iter_el.findtext("LimitBehavior", "Error")
                        prepared_child = bind_workflow_variables(prepare_workflow(parsed_child, caller_answers))
                        opt_child = _IROptimizer(
                            prepared_child,
                            macro_stack=(*self._macro_stack, str(path)),
                        ).run()
                        self.reusable_macros.update(opt_child.reusable_macros)
                        self.loop_macros.update(opt_child.loop_macros)
                        data_outputs = [name for name in output_names if name != iter_out]
                        self.loop_macros[macro_key] = LoopMacroSpec(
                            macro_key=macro_key,
                            macro_path=str(path),
                            kind="iterative",
                            workflow=opt_child.workflow,
                            input_anchors=input_names,
                            output_anchors=data_outputs or output_names,
                            parameters=opt_child.parameters,
                            parameter_expressions=opt_child.parameter_expressions,
                            iteration_input=iter_in,
                            iteration_output=iter_out,
                            iteration_limit=limit,
                            limit_behavior=limit_behavior,
                        )
                    loop_key_by_path[cache_sig] = macro_key
                macro_key = loop_key_by_path[cache_sig]
                parent.tool_type = "MacroLoopCall"
                parent.metadata["loop_macro_key"] = macro_key
                parent.metadata["macro_call_answers"] = caller_answers
                parent.output_anchors = [AnchorIR(name, "output") for name in self.loop_macros[macro_key].output_anchors]
                self.provenance[parent.node_id] = {
                    "status": "loop_macro_call",
                    "target_node_id": parent.node_id,
                    "reason": f"{self.loop_macros[macro_key].kind}_macro:{macro_key}",
                }
                continue

            # Case 1b: Standard Macro invoked >= 2 times -> try reusable subgraph extraction
            if counts_by_path[str(path)] >= 2:
                reusable_ok = str(path) in reusable_key_by_path
                if not reusable_ok:
                    parsed_child = XmlWorkflowParser().parse_xml(xml, path)
                    parsed_child.metadata["embedded_macros"] = embedded
                    try:
                        if question_manifest(root):
                            prepared_child, param_exprs, param_specs = prepare_parameters(parsed_child, caller_answers)
                        else:
                            prepared_child = bind_workflow_variables(prepare_workflow(parsed_child, caller_answers))
                            param_exprs, param_specs = {}, []
                        opt_child = _IROptimizer(
                            prepared_child,
                            parameters=param_specs,
                            parameter_expressions=param_exprs,
                            macro_stack=(*self._macro_stack, str(path)),
                        ).run()
                        macro_key = allocate_key(path.stem)
                        self.reusable_macros.update(opt_child.reusable_macros)
                        self.loop_macros.update(opt_child.loop_macros)
                        self.reusable_macros[macro_key] = MacroSubgraphSpec(
                            macro_key=macro_key,
                            macro_path=str(path),
                            workflow=opt_child.workflow,
                            input_anchors=input_names,
                            output_anchors=output_names,
                            parameters=opt_child.parameters,
                            parameter_expressions=opt_child.parameter_expressions,
                        )
                        reusable_key_by_path[str(path)] = macro_key
                        reusable_ok = True
                    except UnsupportedLowering:
                        reusable_ok = False
                if reusable_ok:
                    macro_key = reusable_key_by_path[str(path)]
                    parent.tool_type = "MacroSubgraphCall"
                    parent.metadata["reusable_macro_key"] = macro_key
                    parent.metadata["macro_call_answers"] = caller_answers
                    parent.output_anchors = [AnchorIR(name, "output") for name in output_names]
                    self.provenance[parent.node_id] = {
                        "status": "reusable_macro_call",
                        "target_node_id": parent.node_id,
                        "reason": f"reusable_macro:{macro_key}",
                    }
                    continue

            # Case 1c: Single-call (or structurally specialized) Standard Macro -> inline & strip boundaries
            parsed_child = XmlWorkflowParser().parse_xml(xml, path)
            parsed_child.metadata["embedded_macros"] = embedded
            prepared_child = bind_workflow_variables(prepare_workflow(parsed_child, caller_answers))
            opt_child = _IROptimizer(
                prepared_child,
                macro_stack=(*self._macro_stack, str(path)),
            ).run()
            self.reusable_macros.update(opt_child.reusable_macros)
            self.loop_macros.update(opt_child.loop_macros)
            self._inline_standard_macro(parent, opt_child.workflow, boundary_names, str(path))

    def _prepare_macro_body(
        self,
        macro: WorkflowIR,
        static_answers: dict[str, Any],
        *,
        dynamic_questions: list[str],
    ) -> tuple[WorkflowIR, dict[tuple[str, tuple[Any, ...]], ExpressionNode], list[dict[str, Any]]]:
        from alteryx2python.runtime.app_config import prepare_workflow
        from alteryx2python.runtime.variables import bind_workflow_variables

        # Try full dynamic parameter preparation first; if unsupported (e.g. ControlParam raw replace),
        # keep a named ParameterExpression where literal probing applies or preserve Question token.
        try:
            return prepare_parameters(macro, static_answers)
        except UnsupportedLowering:
            prepared = bind_workflow_variables(prepare_workflow(macro, static_answers))
            specs = [
                {"name": name, "python_name": _slug(name), "kind": "TextBox", "default": "", "required": False, "choices": []}
                for name in dynamic_questions
            ]
            return prepared, {}, specs

    def _inline_standard_macro(
        self,
        parent: NodeIR,
        child: WorkflowIR,
        boundary_names: dict[str, str],
        macro_path: str,
    ) -> None:
        prefix = f"{parent.node_id}__"
        parent_container = parent.config.get("container_id") or _norm_cfg(parent).get("container_id")
        incoming = [e for e in self.workflow.edges if e.target_node_id == parent.node_id]
        outgoing = [e for e in self.workflow.edges if e.source_node_id == parent.node_id]
        self.workflow.edges = [
            e for e in self.workflow.edges
            if e.target_node_id != parent.node_id and e.source_node_id != parent.node_id
        ]
        self.workflow.nodes = [n for n in self.workflow.nodes if n.node_id != parent.node_id]

        child_in_edges: dict[str, list[EdgeIR]] = {}
        child_out_edges: dict[str, list[EdgeIR]] = {}
        for edge in child.edges:
            child_in_edges.setdefault(edge.target_node_id, []).append(edge)
            child_out_edges.setdefault(edge.source_node_id, []).append(edge)

        macro_inputs = [n for n in child.nodes if n.tool_type in {"MacroInput", "MacroBoundaryInput"}]
        macro_outputs = [n for n in child.nodes if n.tool_type == "MacroOutput"]
        bypassed_ids: set[str] = set()

        # Map each MacroInput directly from outer incoming edge to inner target nodes when connected
        input_source_map: dict[str, tuple[str, str]] = {}
        for m_in in macro_inputs:
            in_name = boundary_names.get(m_in.source_tool_id or m_in.node_id) or _norm_cfg(m_in).get("name") or "Input"
            matches = [e for e in incoming if e.target_anchor == in_name]
            if not matches and len(incoming) == 1 and len(macro_inputs) == 1:
                matches = incoming
            if len(matches) == 1:
                input_source_map[m_in.node_id] = (matches[0].source_node_id, matches[0].source_anchor)
                bypassed_ids.add(m_in.node_id)
            elif len(matches) > 1:
                raise UnsupportedLowering(f"Ambiguous macro input binding: {macro_path}/{in_name}")

        # Map each MacroOutput's upstream source to outer outgoing consumers
        output_source_map: dict[str, tuple[str, str]] = {}
        for m_out in macro_outputs:
            out_name = boundary_names.get(m_out.source_tool_id or m_out.node_id) or _norm_cfg(m_out).get("name") or "Output"
            up_edges = child_in_edges.get(m_out.node_id, [])
            if len(up_edges) == 1:
                up = up_edges[0]
                if up.source_node_id in input_source_map:
                    output_source_map[out_name] = input_source_map[up.source_node_id]
                else:
                    output_source_map[out_name] = (prefix + up.source_node_id, up.source_anchor)
                bypassed_ids.add(m_out.node_id)

        first_inlined_id: str | None = None
        for node in child.nodes:
            if node.node_id in bypassed_ids:
                continue
            cloned = deepcopy(node)
            cloned.node_id = prefix + node.node_id
            if first_inlined_id is None:
                first_inlined_id = cloned.node_id
            cfg = _norm_cfg(cloned)
            if cloned.config.get("container_id"):
                cloned.config["container_id"] = prefix + str(cloned.config["container_id"])
            elif parent_container:
                cloned.config["container_id"] = parent_container
            if cfg.get("container_id"):
                cfg["container_id"] = prefix + str(cfg["container_id"])
            elif parent_container and isinstance(cfg, dict):
                cfg["container_id"] = parent_container
            if cloned.config.get("child_node_ids"):
                cloned.config["child_node_ids"] = [prefix + str(v) for v in cloned.config["child_node_ids"]]
            if cfg.get("child_node_ids"):
                cfg["child_node_ids"] = [prefix + str(v) for v in cfg["child_node_ids"]]
            cloned.metadata.setdefault("macro_source", macro_path)
            cloned.metadata["macro_parent"] = (
                prefix + str(cloned.metadata["macro_parent"])
                if cloned.metadata.get("macro_parent")
                else parent.node_id
            )
            self.workflow.nodes.append(cloned)
            self.provenance[cloned.node_id] = {
                "status": "retained",
                "target_node_id": cloned.node_id,
                "reason": f"inlined_from:{parent.node_id}",
            }

        for edge in child.edges:
            if edge.target_node_id in bypassed_ids:
                continue
            if edge.source_node_id in input_source_map:
                src_node, src_anchor = input_source_map[edge.source_node_id]
            else:
                src_node, src_anchor = prefix + edge.source_node_id, edge.source_anchor
            self.workflow.edges.append(
                replace(
                    edge,
                    edge_id=f"{prefix}{edge.edge_id}",
                    source_node_id=src_node,
                    source_anchor=src_anchor,
                    target_node_id=prefix + edge.target_node_id,
                )
            )

        for out_edge in outgoing:
            mapped = output_source_map.get(out_edge.source_anchor)
            if mapped is None and len(output_source_map) == 1:
                mapped = next(iter(output_source_map.values()))
            if mapped is None:
                raise UnsupportedLowering(f"Unmapped macro output anchor {out_edge.source_anchor!r} on {macro_path}")
            self.workflow.edges.append(
                replace(
                    out_edge,
                    source_node_id=mapped[0],
                    source_anchor=mapped[1],
                )
            )

        self._record_elimination(parent.node_id, first_inlined_id, "inlined_macro", f"inlined:{Path(macro_path).name}")

    # ------------------------------------------------------------------
    # Pass 2: Fold 1-row TextInput + AppendFields into workflow parameters
    # ------------------------------------------------------------------
    def _fold_single_row_parameter_tables(self) -> None:
        from alteryx2python.tools.textinput import _infer_types, _normalize_row

        by_id = {n.node_id: n for n in self.workflow.nodes}
        incoming: dict[str, list[EdgeIR]] = {}
        outgoing: dict[str, list[EdgeIR]] = {}
        for edge in self.workflow.edges:
            incoming.setdefault(edge.target_node_id, []).append(edge)
            outgoing.setdefault(edge.source_node_id, []).append(edge)

        existing_param_names = {p["name"] for p in self.parameters}
        cell_bindings: dict[tuple[str, int, int], str] = {}
        for binding in self.parameter_bindings:
            if binding.get("kind") == "cell" and len(binding.get("path", ())) == 3 and binding["path"][0] == "rows":
                cell_bindings[(binding["node_id"], int(binding["path"][1]), int(binding["path"][2]))] = binding["name"]

        for append_node in list(self.workflow.nodes):
            if append_node.tool_type != "AppendFields":
                continue
            inc = incoming.get(append_node.node_id, [])
            if len(inc) != 2:
                continue
            by_anchor = {e.target_anchor: e for e in inc}
            if set(by_anchor.keys()) != {"Targets", "Source"}:
                continue
            source_edge, target_edge = by_anchor["Source"], by_anchor["Targets"]
            source_node = by_id.get(source_edge.source_node_id)
            target_node = by_id.get(target_edge.source_node_id)
            if source_node is None or target_node is None or source_node.tool_type != "TextInput":
                continue
            if incoming.get(source_node.node_id) or len(outgoing.get(source_node.node_id, [])) != 1:
                continue
            if _container_scope(source_node, by_id) != _container_scope(append_node, by_id):
                continue

            append_cfg = _norm_cfg(append_node)
            selection = append_cfg.get("select_fields", [])
            if selection and not (
                len(selection) == 1
                and selection[0].get("source") == "*Unknown"
                and selection[0].get("selected", True)
                and not selection[0].get("rename")
                and not selection[0].get("dtype")
            ):
                continue

            src_cfg = _norm_cfg(source_node)
            col_names = [str(f) for f in src_cfg.get("fields", [])]
            rows = src_cfg.get("rows", [])
            if (
                not col_names
                or len(col_names) != len({c.casefold() for c in col_names})
                or not isinstance(rows, list)
                or len(rows) != 1
                or not isinstance(rows[0], list)
            ):
                continue

            target_cols = _known_output_columns(target_node, by_id, incoming)
            if target_cols is not None and ({c.casefold() for c in target_cols} & {c.casefold() for c in col_names}):
                continue
            if target_cols is None:
                # Require statically known target columns or provable drop of all lifted columns
                dropped = _columns_provably_dropped_before_sinks(append_node.node_id, set(col_names), self.workflow, by_id)
                if dropped != set(col_names):
                    continue

            normalized_row = _normalize_row(rows[0], col_names)
            # A null bound cell can acquire a type at runtime. Keep TextInput inference
            # instead of substituting the raw Question value into downstream expressions.
            if any(
                value is None and (source_node.node_id, 0, col_idx) in cell_bindings
                for col_idx, value in enumerate(normalized_row)
            ):
                continue
            inferred_frame = _infer_types(pd.DataFrame([normalized_row], columns=col_names, dtype=object))
            inferred_record = inferred_frame.to_dict("records")[0]

            col_to_param: dict[str, ParameterExpression] = {}
            for col_idx, col_name in enumerate(col_names):
                bound_q = cell_bindings.get((source_node.node_id, 0, col_idx))
                if bound_q is not None:
                    param_name = bound_q
                else:
                    base = _slug(col_name)
                    param_name = base
                    suffix = 2
                    while param_name in existing_param_names:
                        param_name = f"{base}_{suffix}"
                        suffix += 1
                    existing_param_names.add(param_name)
                    raw_val = inferred_record[col_name]
                    if pd.isna(raw_val):
                        default_val: Any = None
                        kind = "TextBox"
                    elif isinstance(raw_val, pd.Timestamp):
                        default_val = raw_val.date().isoformat()
                        kind = "Date"
                    elif isinstance(raw_val, bool):
                        default_val = bool(raw_val)
                        kind = "BooleanGroup"
                    elif isinstance(raw_val, int):
                        default_val = int(raw_val)
                        kind = "NumericUpDown"
                    elif isinstance(raw_val, float):
                        default_val = float(raw_val)
                        kind = "NumericUpDown"
                    else:
                        default_val = str(raw_val)
                        kind = "TextBox"
                    self.parameters.append({
                        "name": param_name,
                        "python_name": _slug(param_name),
                        "kind": kind,
                        "default": default_val,
                        "minimum": None,
                        "maximum": None,
                        "required": False,
                        "choices": [],
                        "source_node_id": source_node.node_id,
                        "folded_from_column": col_name,
                    })
                col_to_param[col_name] = ParameterExpression(param_name)

            dropped_cols = _columns_provably_dropped_before_sinks(
                append_node.node_id, set(col_names), self.workflow, by_id
            )
            surviving_cols = [c for c in col_names if c not in dropped_cols]

            # Rewrite downstream Formula/Filter references before shadowing
            self._propagate_folded_parameters(append_node.node_id, col_to_param, by_id, outgoing)

            if surviving_cols:
                # Materialize only surviving scalar columns as lightweight Formula assignments
                formula_fields = [
                    {
                        "field": col_name,
                        "expression": f"[Question.{col_to_param[col_name].name}]",
                        "enabled": True,
                        "type": None,
                        "size": None,
                    }
                    for col_name in surviving_cols
                ]
                append_node.tool_type = "Formula"
                append_node.tool_name = "Formula"
                append_node.input_anchors = [AnchorIR("Input", "input")]
                append_node.output_anchors = [AnchorIR("Output", "output")]
                _set_norm_cfg(append_node, {"formula_fields": formula_fields})
                for idx, col_name in enumerate(surviving_cols):
                    self.parameter_expressions[(append_node.node_id, ("formula_fields", idx, "expression"))] = col_to_param[col_name]
                self.workflow.edges = [
                    replace(e, target_anchor="Input") if e.edge_id == target_edge.edge_id else e
                    for e in self.workflow.edges
                    if e.edge_id != source_edge.edge_id
                ]
                self.workflow.nodes = [n for n in self.workflow.nodes if n.node_id != source_node.node_id]
                self._record_elimination(source_node.node_id, append_node.node_id, "eliminated", "folded_parameter_table")
            else:
                # Rewire AppendFields consumers directly to target_edge source
                rewired_edges: list[EdgeIR] = []
                for edge in self.workflow.edges:
                    if edge.edge_id in {source_edge.edge_id, target_edge.edge_id}:
                        continue
                    if edge.source_node_id == append_node.node_id:
                        rewired_edges.append(
                            replace(edge, source_node_id=target_edge.source_node_id, source_anchor=target_edge.source_anchor)
                        )
                    else:
                        rewired_edges.append(edge)
                self.workflow.edges = rewired_edges
                self.workflow.nodes = [
                    n for n in self.workflow.nodes if n.node_id not in {source_node.node_id, append_node.node_id}
                ]
                self._record_elimination(source_node.node_id, target_edge.source_node_id, "eliminated", "folded_parameter_table")
                self._record_elimination(append_node.node_id, target_edge.source_node_id, "eliminated", "folded_parameter_append")

            # Remove consumed cell bindings
            self.parameter_bindings = [
                b for b in self.parameter_bindings
                if not (b.get("kind") == "cell" and b.get("node_id") == source_node.node_id)
            ]
            by_id = {n.node_id: n for n in self.workflow.nodes}
            incoming.clear()
            outgoing.clear()
            for edge in self.workflow.edges:
                incoming.setdefault(edge.target_node_id, []).append(edge)
                outgoing.setdefault(edge.source_node_id, []).append(edge)

    def _propagate_folded_parameters(
        self,
        start_node_id: str,
        col_to_param: dict[str, ParameterExpression],
        by_id: dict[str, NodeIR],
        outgoing: dict[str, list[EdgeIR]],
    ) -> None:
        visited: set[tuple[str, frozenset[str]]] = set()

        def walk(node_id: str, active: dict[str, ParameterExpression]) -> None:
            if not active:
                return
            key = (node_id, frozenset(active.keys()))
            if key in visited:
                return
            visited.add(key)
            node = by_id[node_id]
            cfg = _norm_cfg(node)
            next_active = dict(active)

            if node.tool_type == "Formula":
                for idx, field_entry in enumerate(cfg.get("formula_fields", [])):
                    if not field_entry.get("enabled", True):
                        continue
                    expr_key = (node_id, ("formula_fields", idx, "expression"))
                    parsed = self.parameter_expressions.get(expr_key) or parse_expression(field_entry["expression"])
                    rewritten, changed = _rewrite_field_refs(parsed, next_active)
                    if changed:
                        self.parameter_expressions[expr_key] = rewritten
                        field_entry["expression"] = _expression_to_alteryx(rewritten)
                    out_col = str(field_entry.get("field", ""))
                    for k in list(next_active.keys()):
                        if k.casefold() == out_col.casefold():
                            next_active.pop(k)
            elif node.tool_type == "Filter":
                expr_key = (node_id, ("expression",))
                parsed = self.parameter_expressions.get(expr_key) or parse_expression(cfg["expression"])
                rewritten, changed = _rewrite_field_refs(parsed, next_active)
                if changed:
                    self.parameter_expressions[expr_key] = rewritten
                    cfg["expression"] = _expression_to_alteryx(rewritten)
            elif node.tool_type == "Select":
                s_fields = cfg.get("select_fields", [])
                has_unknown = any(f.get("source") == "*Unknown" and f.get("selected", True) for f in s_fields)
                explicit = {str(f["source"]).casefold(): f for f in s_fields if f.get("source") != "*Unknown"}
                updated: dict[str, ParameterExpression] = {}
                for k, param_expr in next_active.items():
                    entry = explicit.get(k.casefold())
                    if entry is not None:
                        if entry.get("selected", True):
                            new_name = str(entry.get("rename") or entry["source"])
                            updated[new_name] = param_expr
                    elif has_unknown:
                        updated[k] = param_expr
                next_active = updated

            for edge in outgoing.get(node_id, []):
                walk(edge.target_node_id, next_active)

        for edge in outgoing.get(start_node_id, []):
            walk(edge.target_node_id, col_to_param)

    # ------------------------------------------------------------------
    # Pass 3: Prune UI no-ops, passthrough Selects, and dead branches
    # ------------------------------------------------------------------
    def _prune_noop_and_dead_branches(self) -> bool:
        changed = False
        by_id = {n.node_id: n for n in self.workflow.nodes}

        # 3a. Remove non-functional UI nodes & static enabled ToolContainers
        removable_containers: set[str] = set()
        for node in self.workflow.nodes:
            if node.tool_type == "ToolContainer":
                cfg = _norm_cfg(node)
                if not cfg.get("disabled") and not node.metadata.get("disabled_parameter"):
                    removable_containers.add(node.node_id)

        if removable_containers:
            for node in self.workflow.nodes:
                cid = node.config.get("container_id") or _norm_cfg(node).get("container_id")
                while cid in removable_containers:
                    parent_c = by_id[cid]
                    cid = parent_c.config.get("container_id") or _norm_cfg(parent_c).get("container_id")
                if "container_id" in node.config:
                    node.config["container_id"] = cid
                if isinstance(_norm_cfg(node), dict) and "container_id" in _norm_cfg(node):
                    _norm_cfg(node)["container_id"] = cid

        kept_nodes: list[NodeIR] = []
        removed_ids: set[str] = set()
        for node in self.workflow.nodes:
            if node.tool_type in UI_NOOP_TOOLS:
                removed_ids.add(node.node_id)
                self._record_elimination(node.node_id, None, "eliminated", f"ui_noop:{node.tool_type}")
                changed = True
            elif node.node_id in removable_containers:
                removed_ids.add(node.node_id)
                self._record_elimination(node.node_id, None, "eliminated", "enabled_tool_container")
                changed = True
            else:
                kept_nodes.append(node)

        if removed_ids:
            self.workflow.nodes = kept_nodes
            self.workflow.edges = [
                e for e in self.workflow.edges
                if e.source_node_id not in removed_ids and e.target_node_id not in removed_ids
            ]
            by_id = {n.node_id: n for n in self.workflow.nodes}

        # 3b. Bypass identity Select nodes
        incoming: dict[str, list[EdgeIR]] = {}
        outgoing: dict[str, list[EdgeIR]] = {}
        for edge in self.workflow.edges:
            incoming.setdefault(edge.target_node_id, []).append(edge)
            outgoing.setdefault(edge.source_node_id, []).append(edge)

        for node in list(self.workflow.nodes):
            if node.tool_type != "Select":
                continue
            inc = incoming.get(node.node_id, [])
            outs = outgoing.get(node.node_id, [])
            if len(inc) != 1 or not outs:
                continue
            if _is_identity_select(_norm_cfg(node)):
                up = inc[0]
                if _container_scope(by_id[up.source_node_id], by_id) != _container_scope(node, by_id):
                    continue
                self.workflow.edges = [
                    replace(e, source_node_id=up.source_node_id, source_anchor=up.source_anchor)
                    if e.source_node_id == node.node_id
                    else e
                    for e in self.workflow.edges
                    if e.edge_id != up.edge_id
                ]
                self.workflow.nodes = [n for n in self.workflow.nodes if n.node_id != node.node_id]
                self._record_elimination(node.node_id, up.source_node_id, "eliminated", "identity_select")
                return True

        # 3c. Backward reachability from observable sinks (only when workflow has explicit sinks)
        has_explicit_sinks = any(n.tool_type in OBSERVABLE_SINK_TOOLS for n in self.workflow.nodes)
        if has_explicit_sinks:
            incoming.clear()
            outgoing.clear()
            for edge in self.workflow.edges:
                incoming.setdefault(edge.target_node_id, []).append(edge)
                outgoing.setdefault(edge.source_node_id, []).append(edge)
            by_id = {n.node_id: n for n in self.workflow.nodes}

            roots: list[str] = [
                n.node_id
                for n in self.workflow.nodes
                if n.tool_type in OBSERVABLE_SINK_TOOLS
                or (n.tool_type == "ControlContainer" and outgoing.get(n.node_id))
            ]
            # Preserve active containers that guard reachable nodes
            reachable: set[str] = set()
            stack = list(roots)
            while stack:
                nid = stack.pop()
                if nid in reachable or nid not in by_id:
                    continue
                reachable.add(nid)
                for edge in incoming.get(nid, []):
                    stack.append(edge.source_node_id)
                for cid in _container_scope(by_id[nid], by_id):
                    stack.append(cid)
                    # If ControlContainer has Control input, keep its upstream too
                    for edge in incoming.get(cid, []):
                        stack.append(edge.source_node_id)

            dead_ids = {n.node_id for n in self.workflow.nodes} - reachable
            if dead_ids:
                for did in sorted(dead_ids):
                    self._record_elimination(did, None, "eliminated", "unreachable_dead_branch")
                self.workflow.nodes = [n for n in self.workflow.nodes if n.node_id in reachable]
                self.workflow.edges = [
                    e for e in self.workflow.edges
                    if e.source_node_id in reachable and e.target_node_id in reachable
                ]
                changed = True

        return changed

    # ------------------------------------------------------------------
    # Pass 4: Algebraic Select -> Select fusion
    # ------------------------------------------------------------------
    def _fuse_select_chains(self) -> bool:
        by_id = {n.node_id: n for n in self.workflow.nodes}
        incoming: dict[str, list[EdgeIR]] = {}
        outgoing: dict[str, list[EdgeIR]] = {}
        for edge in self.workflow.edges:
            incoming.setdefault(edge.target_node_id, []).append(edge)
            outgoing.setdefault(edge.source_node_id, []).append(edge)

        for first in list(self.workflow.nodes):
            if first.tool_type != "Select":
                continue
            outs = outgoing.get(first.node_id, [])
            if len(outs) != 1:
                continue
            second = by_id.get(outs[0].target_node_id)
            if second is None or second.tool_type != "Select":
                continue
            if len(incoming.get(second.node_id, [])) != 1:
                continue
            if _container_scope(first, by_id) != _container_scope(second, by_id):
                continue

            composed = _compose_select_configs(_norm_cfg(first), _norm_cfg(second))
            if composed is None:
                continue

            _set_norm_cfg(first, composed)
            first.expected_output_schema = deepcopy(second.expected_output_schema)
            bridge_edge_id = outs[0].edge_id
            self.workflow.edges = [
                replace(e, source_node_id=first.node_id, source_anchor="Output")
                if e.source_node_id == second.node_id
                else e
                for e in self.workflow.edges
                if e.edge_id != bridge_edge_id
            ]
            self.workflow.nodes = [n for n in self.workflow.nodes if n.node_id != second.node_id]
            self._record_elimination(second.node_id, first.node_id, "fused", "fused_select_chain")
            return True
        return False

    # ------------------------------------------------------------------
    # Pass 5: Consecutive Formula -> Formula fusion
    # ------------------------------------------------------------------
    def _fuse_formulas(self) -> bool:
        by_id = {n.node_id: n for n in self.workflow.nodes}
        incoming: dict[str, list[EdgeIR]] = {}
        outgoing: dict[str, list[EdgeIR]] = {}
        for edge in self.workflow.edges:
            incoming.setdefault(edge.target_node_id, []).append(edge)
            outgoing.setdefault(edge.source_node_id, []).append(edge)

        for first in list(self.workflow.nodes):
            if first.tool_type != "Formula":
                continue
            outs = outgoing.get(first.node_id, [])
            if len(outs) != 1:
                continue
            second = by_id.get(outs[0].target_node_id)
            if second is None or second.tool_type != "Formula":
                continue
            if len(incoming.get(second.node_id, [])) != 1:
                continue
            if _container_scope(first, by_id) != _container_scope(second, by_id):
                continue
            consts1 = first.metadata.get("workflow_constants") or self.workflow.metadata.get("workflow_constants") or {}
            consts2 = second.metadata.get("workflow_constants") or self.workflow.metadata.get("workflow_constants") or {}
            if not _compatible_formula_constants(_norm_cfg(first), _norm_cfg(second), consts1, consts2):
                continue
            if consts1 or consts2:
                first.metadata["workflow_constants"] = {**consts1, **consts2}

            cfg1, cfg2 = _norm_cfg(first), _norm_cfg(second)
            fields1 = list(cfg1.get("formula_fields", []))
            fields2 = list(cfg2.get("formula_fields", []))
            offset = len(fields1)

            for idx in range(len(fields2)):
                old_key = (second.node_id, ("formula_fields", idx, "expression"))
                if old_key in self.parameter_expressions:
                    self.parameter_expressions[(first.node_id, ("formula_fields", offset + idx, "expression"))] = (
                        self.parameter_expressions.pop(old_key)
                    )

            cfg1["formula_fields"] = fields1 + fields2
            first.expected_output_schema = deepcopy(second.expected_output_schema or first.expected_output_schema)
            bridge_edge_id = outs[0].edge_id
            self.workflow.edges = [
                replace(e, source_node_id=first.node_id, source_anchor="Output")
                if e.source_node_id == second.node_id
                else e
                for e in self.workflow.edges
                if e.edge_id != bridge_edge_id
            ]
            self.workflow.nodes = [n for n in self.workflow.nodes if n.node_id != second.node_id]
            self._record_elimination(second.node_id, first.node_id, "fused", "fused_formula_chain")
            return True
        return False

    # ------------------------------------------------------------------
    # Pass 6: Conservative dead-column pruning on Select & Formula nodes
    # ------------------------------------------------------------------
    def _prune_dead_columns(self) -> bool:
        changed = False
        by_id = {n.node_id: n for n in self.workflow.nodes}
        outgoing: dict[str, list[EdgeIR]] = {}
        for edge in self.workflow.edges:
            outgoing.setdefault(edge.source_node_id, []).append(edge)

        for node in self.workflow.nodes:
            outs = outgoing.get(node.node_id, [])
            if not outs:
                continue
            cfg = _norm_cfg(node)
            if node.tool_type == "Select":
                s_fields = cfg.get("select_fields", [])
                selected_explicit = [
                    f for f in s_fields if f.get("selected", True) and f.get("source") != "*Unknown"
                ]
                if len(selected_explicit) <= 1:
                    continue
                out_names = {str(f.get("rename") or f["source"]) for f in selected_explicit}
                dropped = _columns_provably_dropped_before_sinks(node.node_id, out_names, self.workflow, by_id)
                if not dropped:
                    continue
                used_downstream = _columns_read_before_drop(node.node_id, dropped, self.workflow, by_id, self.parameter_expressions)
                truly_dead = {c.casefold() for c in (dropped - used_downstream)}
                if not truly_dead:
                    continue
                for f in s_fields:
                    out_col = str(f.get("rename") or f.get("source", ""))
                    if f.get("selected", True) and f.get("source") != "*Unknown" and out_col.casefold() in truly_dead:
                        f["selected"] = False
                        changed = True
        return changed


def _columns_read_before_drop(
    start_node_id: str,
    candidates: set[str],
    workflow: WorkflowIR,
    by_id: dict[str, NodeIR],
    param_exprs: dict[tuple[str, tuple[Any, ...]], ExpressionNode],
) -> set[str]:
    outgoing: dict[str, list[EdgeIR]] = {}
    for edge in workflow.edges:
        outgoing.setdefault(edge.source_node_id, []).append(edge)

    lower_to_orig = {c.casefold(): c for c in candidates}
    used: set[str] = set()
    visited: set[str] = set()

    def walk(node_id: str) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        node = by_id[node_id]
        cfg = _norm_cfg(node)
        kind = node.tool_type

        if kind == "Select":
            s_fields = cfg.get("select_fields", [])
            has_unknown = any(f.get("source") == "*Unknown" and f.get("selected", True) for f in s_fields)
            kept = {
                str(f["source"]).casefold()
                for f in s_fields
                if f.get("selected", True) and f.get("source") != "*Unknown"
            }
            if not has_unknown and not (kept & set(lower_to_orig.keys())):
                return
            for edge in outgoing.get(node_id, []):
                walk(edge.target_node_id)
            return

        if kind == "Formula":
            for idx, f in enumerate(cfg.get("formula_fields", [])):
                if not f.get("enabled", True):
                    continue
                ast_node = param_exprs.get((node_id, ("formula_fields", idx, "expression"))) or parse_expression(f["expression"])
                for ref in _referenced_fields(ast_node):
                    if ref.casefold() in lower_to_orig:
                        used.add(lower_to_orig[ref.casefold()])
        elif kind == "Filter":
            ast_node = param_exprs.get((node_id, ("expression",))) or parse_expression(cfg["expression"])
            for ref in _referenced_fields(ast_node):
                if ref.casefold() in lower_to_orig:
                    used.add(lower_to_orig[ref.casefold()])
        elif kind == "Sort":
            for f in cfg.get("sort_fields", []):
                ref = str(f.get("field", ""))
                if ref.casefold() in lower_to_orig:
                    used.add(lower_to_orig[ref.casefold()])
        elif kind == "Unique":
            u_fields = cfg.get("unique_fields")
            if not u_fields:
                used.update(candidates)
            else:
                for ref in u_fields:
                    if str(ref).casefold() in lower_to_orig:
                        used.add(lower_to_orig[str(ref).casefold()])
        elif kind in {"Sample", "RecordID"}:
            for ref in cfg.get("group_fields", []):
                if str(ref).casefold() in lower_to_orig:
                    used.add(lower_to_orig[str(ref).casefold()])
        else:
            used.update(candidates)
            return

        for edge in outgoing.get(node_id, []):
            walk(edge.target_node_id)

    for edge in outgoing.get(start_node_id, []):
        walk(edge.target_node_id)
    return used


def _compatible_formula_constants(
    cfg1: dict[str, Any],
    cfg2: dict[str, Any],
    consts1: dict[str, Any],
    consts2: dict[str, Any],
) -> bool:
    if consts1 == consts2:
        return True
    shared_keys = set(consts1.keys()) & set(consts2.keys())
    conflicting = {k for k in shared_keys if consts1[k] != consts2[k]}
    if not conflicting:
        return True
    for cfg in (cfg1, cfg2):
        for entry in cfg.get("formula_fields", []):
            if not entry.get("enabled", True):
                continue
            text = str(entry.get("expression", ""))
            if any(k in text for k in conflicting):
                return False
    return True


def _is_identity_select(cfg: dict[str, Any]) -> bool:
    fields_list = cfg.get("select_fields", [])
    if not fields_list:
        return False
    if cfg.get("order_changed"):
        return False
    if len(fields_list) == 1:
        f = fields_list[0]
        return (
            f.get("source") == "*Unknown"
            and bool(f.get("selected", True))
            and f.get("rename") in (None, "", "*Unknown")
            and not f.get("dtype")
        )
    return False


def _compose_select_configs(cfg1: dict[str, Any], cfg2: dict[str, Any]) -> dict[str, Any] | None:
    """Compose Select_1 -> Select_2 into a single Select config when lossless."""
    from alteryx2python.tools.select import _normalize_select_fields

    fields1 = _normalize_select_fields(cfg1)
    fields2 = _normalize_select_fields(cfg2)
    unknown1 = any(f["source"] == "*Unknown" and f["selected"] for f in fields1)
    unknown2 = any(f["source"] == "*Unknown" and f["selected"] for f in fields2)

    # Map intermediate column name -> Select_1 explicit entry
    produced_by_1: dict[str, dict[str, Any]] = {}
    dropped_by_1: set[str] = set()
    for f1 in fields1:
        if f1["source"] == "*Unknown":
            continue
        if f1["selected"]:
            produced_by_1[str(f1["rename"])] = f1
        else:
            dropped_by_1.add(str(f1["source"]))

    mentioned_in_2 = {str(f2["source"]) for f2 in fields2 if f2["source"] != "*Unknown"}
    composed_fields: list[dict[str, Any]] = []
    excluded_from_unknown: set[str] = set(dropped_by_1)

    for f2 in fields2:
        src2 = str(f2["source"])
        if src2 == "*Unknown":
            if not f2["selected"]:
                continue
            # Expand any explicit Select_1 outputs not mentioned in Select_2
            for mid_name, f1 in produced_by_1.items():
                if mid_name not in mentioned_in_2:
                    composed_fields.append(deepcopy(f1))
                    excluded_from_unknown.add(str(f1["source"]))
            if unknown1:
                composed_fields.append({
                    "source": "*Unknown",
                    "rename": "*Unknown",
                    "dtype": None,
                    "selected": True,
                    "size": None,
                    "forced": False,
                })
            continue

        if not f2["selected"]:
            if src2 in produced_by_1:
                excluded_from_unknown.add(str(produced_by_1[src2]["source"]))
            else:
                excluded_from_unknown.add(src2)
            continue

        # f2 is explicitly selected
        if src2 in produced_by_1:
            f1 = produced_by_1[src2]
            dtype1, size1 = f1.get("dtype"), f1.get("size")
            dtype2, size2 = f2.get("dtype"), f2.get("size")
            if dtype1 is not None and dtype2 is not None and (dtype1, size1) != (dtype2, size2):
                # Avoid losing intermediate narrow width/overflow cast semantics
                return None
            final_dtype = dtype2 if dtype2 is not None else dtype1
            final_size = size2 if dtype2 is not None else size1
            composed_fields.append({
                "source": f1["source"],
                "rename": f2["rename"],
                "dtype": final_dtype,
                "selected": True,
                "size": final_size,
                "forced": bool(f1.get("forced") or f2.get("forced")),
            })
            excluded_from_unknown.add(str(f1["source"]))
        else:
            if src2 in dropped_by_1 or not unknown1:
                # Select_2 references a column dropped by Select_1 -> let runtime raise missing field error
                return None
            composed_fields.append(deepcopy(f2))
            excluded_from_unknown.add(src2)

    if unknown1 and unknown2:
        already_explicit = {str(f["source"]) for f in composed_fields if f["source"] != "*Unknown"}
        for dropped in sorted(excluded_from_unknown - already_explicit):
            composed_fields.append({
                "source": dropped,
                "rename": dropped,
                "dtype": None,
                "selected": False,
                "size": None,
                "forced": False,
            })

    selected_names = [f["rename"] for f in composed_fields if f["selected"] and f["source"] != "*Unknown"]
    if len(selected_names) != len(set(selected_names)):
        return None
    if not composed_fields:
        return None

    return {
        **cfg2,
        "select_fields": composed_fields,
        "order_changed": bool(cfg1.get("order_changed") or cfg2.get("order_changed")),
    }


def optimize_workflow_ir(
    workflow: WorkflowIR,
    *,
    parameters: list[dict[str, Any]] | None = None,
    parameter_bindings: list[dict[str, Any]] | None = None,
    parameter_expressions: dict[tuple[str, tuple[Any, ...]], ExpressionNode] | None = None,
) -> OptimizationResult:
    """Run all deterministic Phase 2 IR optimization passes on workflow."""
    return _IROptimizer(
        workflow,
        parameters=parameters,
        parameter_bindings=parameter_bindings,
        parameter_expressions=parameter_expressions,
    ).run()
