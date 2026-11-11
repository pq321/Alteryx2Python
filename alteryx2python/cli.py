from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

import pandas as pd

from alteryx2python.certification import assert_nodes_certifiable, certification_issues_for_nodes
from alteryx2python.equivalence import run_equivalence, run_equivalence_suite
from alteryx2python.native_runner import run_native
from alteryx2python.compact import build_compact_workflow
from alteryx2python.comparison.dataframe_diff import compare_dataframes
from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.support_surfaces import build_support_map
from alteryx2python.tools.registry import TOOL_REGISTRY


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report, exit_code = args.func(args)
    except Exception as exc:  # pragma: no cover - exercised through subprocess CLI tests
        report = _error_report(args.command, exc)
        exit_code = 2
    _emit_report(report, getattr(args, "log", None))
    return exit_code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alteryx2python")
    subparsers = parser.add_subparsers(dest="command", required=True)

    readable = subparsers.add_parser('readable', help='Phase two: compile preserved workflow IR into standalone editable Python')
    readable.add_argument('source', help='Native workflow, preserved .ir.json, or recognized phase-one .py')
    readable.add_argument('--output', required=True)
    readable.add_argument('--answers', help='JSON file containing default user answers')
    readable.add_argument('--delivery-profile', choices=['html-draft-v1'])
    readable.set_defaults(func=_readable_command)
    benchmark = subparsers.add_parser('benchmark', help='Build or verify the deterministic two-phase benchmark')
    benchmark.add_argument('action', choices=['build', 'run', 'inventory'])
    benchmark.add_argument('--output', required=True)
    benchmark.add_argument('--source')
    benchmark.add_argument('--data', default='examples/readable_benchmark/data/iris.data')
    benchmark.add_argument('--samples', default='D:/Alteryx/Samples/en')
    benchmark.add_argument('--answers')
    benchmark.set_defaults(func=_benchmark_command)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect workflow nodes, edges, tools, and dependencies")
    inspect_parser.add_argument("workflow")
    inspect_parser.add_argument("--compact", action="store_true")
    inspect_parser.add_argument("--log")
    inspect_parser.set_defaults(func=_inspect_command)

    compact_parser = subparsers.add_parser("compact", help="Emit a topology-preserving compact workflow JSON")
    compact_parser.add_argument("workflow")
    compact_parser.add_argument("--log")
    compact_parser.set_defaults(func=_compact_command)

    support_parser = subparsers.add_parser("support-map", help="Emit a change-request support surface map")
    support_parser.add_argument("workflow")
    support_parser.add_argument("--log")
    support_parser.set_defaults(func=_support_map_command)

    generate_parser = subparsers.add_parser("generate", help="Generate a Python script for one workflow")
    generate_parser.add_argument("workflow")
    generate_parser.add_argument("--output", required=True)
    generate_parser.add_argument("--answers", help="JSON file with app/macro question answers")
    generate_parser.add_argument("--log")
    generate_parser.set_defaults(func=_generate_command)

    generate_samples_parser = subparsers.add_parser(
        "generate-samples",
        help="Recursively generate Python scripts for Alteryx sample workflows",
    )
    generate_samples_parser.add_argument("sample_root")
    generate_samples_parser.add_argument("--output-dir", required=True)
    generate_samples_parser.add_argument("--log")
    generate_samples_parser.set_defaults(func=_generate_samples_command)

    run_parser = subparsers.add_parser("run", help="Run a workflow target node through the canonical runtime")
    run_parser.add_argument("workflow")
    run_parser.add_argument("--target-node", required=True)
    run_parser.add_argument("--answers")
    run_parser.add_argument("--data-slice", action="store_true", help="Explicitly skip app configuration for an isolated migration slice")
    run_parser.add_argument("--override-output", action="append", default=[])
    run_parser.add_argument("--log")
    run_parser.set_defaults(func=_run_command)

    compare_parser = subparsers.add_parser("compare", help="Compare actual and expected outputs")
    compare_parser.add_argument("--actual", required=True)
    compare_parser.add_argument("--expected", required=True)
    compare_parser.add_argument("--mode", choices=["bytes", "csv"], default="bytes")
    compare_parser.add_argument("--log")
    compare_parser.set_defaults(func=_compare_command)

    certify_parser = subparsers.add_parser("certify", help="Run, certification-gate, and compare a workflow target")
    certify_parser.add_argument("workflow")
    certify_parser.add_argument("--target-node", required=True)
    certify_parser.add_argument("--expect", required=True)
    certify_parser.add_argument("--compare", choices=["bytes", "csv"], default="bytes")
    certify_parser.add_argument("--override-output", action="append", default=[])
    certify_parser.add_argument("--actual")
    certify_parser.add_argument("--log")
    certify_parser.set_defaults(func=_certify_command)

    generate_workflow_parser = subparsers.add_parser(
        "generate-workflow",
        help="Generate a deterministic data-processing workflow (.yxmd) for equivalence testing",
    )
    generation_mode = generate_workflow_parser.add_mutually_exclusive_group(required=True)
    generation_mode.add_argument("--preset")
    generation_mode.add_argument("--spec", help="JSON graph specification, or existing native workflow/template")
    generate_workflow_parser.add_argument("--output", required=True)
    generate_workflow_parser.add_argument("--python-output", help="Also generate corresponding Python in the same command")
    generate_workflow_parser.add_argument("--csv-out")
    generate_workflow_parser.add_argument("--seed", type=int, default=42)
    generate_workflow_parser.add_argument("--rows", type=int, default=40)
    generate_workflow_parser.add_argument("--log")
    generate_workflow_parser.set_defaults(func=_generate_workflow_command)

    run_native_parser = subparsers.add_parser(
        "run-native",
        help="Run a workflow through a native Alteryx backend (headless engine or Designer CLI)",
    )
    run_native_parser.add_argument("workflow")
    run_native_parser.add_argument("--watch-file")
    run_native_parser.add_argument("--runner", choices=["auto", "engine-cmd", "designer-cli"], default="auto")
    run_native_parser.add_argument("--timeout", type=int, default=240)
    run_native_parser.add_argument("--log")
    run_native_parser.set_defaults(func=_run_native_command)

    equivalence_parser = subparsers.add_parser(
        "equivalence",
        help="Run one workflow natively and through Python, then compare outputs",
    )
    equivalence_parser.add_argument("workflow")
    equivalence_parser.add_argument("--native-csv")
    equivalence_parser.add_argument("--oracle")
    equivalence_parser.add_argument("--runner", choices=["auto", "engine-cmd", "designer-cli"], default="auto")
    equivalence_parser.add_argument("--timeout", type=int, default=240)
    equivalence_parser.add_argument("--per-node", action="store_true", help="Require typed native evidence for every node/output anchor")
    equivalence_parser.add_argument("--output-dir")
    equivalence_parser.add_argument("--engine")
    equivalence_parser.add_argument("--log")
    equivalence_parser.set_defaults(func=_equivalence_command)

    equivalence_suite_parser = subparsers.add_parser(
        "equivalence-suite",
        help="Generate and equivalence-test every preset workflow",
    )
    equivalence_suite_parser.add_argument("--out-dir", required=True)
    equivalence_suite_parser.add_argument("--presets")
    equivalence_suite_parser.add_argument("--seed", type=int, default=42)
    equivalence_suite_parser.add_argument("--rows", type=int, default=40)
    equivalence_suite_parser.add_argument("--runner", choices=["auto", "engine-cmd", "designer-cli"], default="auto")
    equivalence_suite_parser.add_argument("--log")
    equivalence_suite_parser.set_defaults(func=_equivalence_suite_command)

    tools_parser = subparsers.add_parser("tools", help="List the complete official mapping and declared executable profiles")
    tools_parser.add_argument("--tool")
    tools_parser.add_argument("--output")
    tools_parser.set_defaults(func=_tools_command)
    export_parser = subparsers.add_parser("workflow-export", help="Export a native workflow as an editable JSON graph, preserving its XML")
    export_parser.add_argument("workflow")
    export_parser.add_argument("--output", required=True)
    export_parser.set_defaults(func=_workflow_export_command)
    edit_parser = subparsers.add_parser("workflow-edit", help="Add/remove nodes and connections without discarding unrelated native XML")
    edit_parser.add_argument("workflow")
    edit_parser.add_argument("--output", required=True)
    edit_parser.add_argument("--add-node", action="append", default=[], help="NodeSpec JSON file")
    edit_parser.add_argument("--remove-node", action="append", default=[])
    edit_parser.add_argument("--connect", action="append", default=[], help="ID:ANCHOR=ID:ANCHOR")
    edit_parser.add_argument("--disconnect", action="append", default=[])
    edit_parser.set_defaults(func=_workflow_edit_command)
    template_parser = subparsers.add_parser("node-template", help="Extract an exact node template from an installed sample or user workflow")
    template_parser.add_argument("workflow")
    template_parser.add_argument("--node", required=True)
    template_parser.add_argument("--new-id", help="Assign a new native ToolID to the extracted template")
    template_parser.add_argument("--output", required=True)
    template_parser.set_defaults(func=_node_template_command)
    validate_parser = subparsers.add_parser("validate-workflow", help="Validate graph structure and report unsupported execution profiles")
    validate_parser.add_argument("workflow")
    validate_parser.add_argument("--require-executable", action="store_true")
    validate_parser.set_defaults(func=_validate_workflow_command)
    questions_parser = subparsers.add_parser("questions", help="List native app/macro questions and defaults")
    questions_parser.add_argument("workflow")
    questions_parser.set_defaults(func=_questions_command)
    configure_parser = subparsers.add_parser("configure-workflow", help="Bind answers and apply native question Actions to a workflow copy")
    configure_parser.add_argument("workflow")
    configure_parser.add_argument("--answers", required=True)
    configure_parser.add_argument("--output", required=True)
    configure_parser.add_argument("--defaults-only", action="store_true", help="Keep the native interface and Actions; update only question defaults")
    configure_parser.set_defaults(func=_configure_workflow_command)
    python_parser = subparsers.add_parser("run-python", help="Run the complete graph and export typed per-node results")
    python_parser.add_argument("workflow")
    python_parser.add_argument("--answers")
    python_parser.add_argument("--output-dir", required=True)
    python_parser.set_defaults(func=_run_python_command)
    proof_parser = subparsers.add_parser("proof-suite", help="Run a tool/configuration case manifest with per-node native evidence")
    proof_parser.add_argument("--cases", required=True)
    proof_parser.add_argument("--out-dir", required=True)
    proof_parser.add_argument("--engine")
    proof_parser.add_argument("--timeout", type=int, default=120)
    proof_parser.set_defaults(func=_proof_suite_command)

    for command_parser in subparsers.choices.values():
        if "--log" not in command_parser._option_string_actions:
            command_parser.add_argument("--log")
    return parser


def _inspect_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    workflow = XmlWorkflowParser().parse(Path(args.workflow))
    if args.compact:
        return _compact_report(workflow), 0
    unsupported_nodes = _unsupported_nodes(workflow)
    report = {
        "command": "inspect",
        "status": "ok",
        "workflow": _workflow_summary(workflow),
        "nodes": [_node_summary(node) for node in workflow.nodes],
        "edges": [
            {
                "edge_id": edge.edge_id,
                "source_node_id": edge.source_node_id,
                "source_anchor": edge.source_anchor,
                "target_node_id": edge.target_node_id,
                "target_anchor": edge.target_anchor,
            }
            for edge in workflow.edges
        ],
        "tool_types": sorted({node.tool_type for node in workflow.nodes}),
        "external_dependencies": list(workflow.external_dependencies),
        "unsupported_nodes": unsupported_nodes,
        "warnings": list(workflow.warnings),
    }
    return report, 0


def _compact_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    workflow = XmlWorkflowParser().parse(Path(args.workflow))
    return _compact_report(workflow), 0


def _support_map_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    workflow = XmlWorkflowParser().parse(Path(args.workflow))
    return {
        "command": "support-map",
        "status": "ok",
        "support_map": build_support_map(workflow),
    }, 0


def _compact_report(workflow: Any) -> dict[str, Any]:
    return {
        "command": "compact",
        "status": "ok",
        "compact_workflow": build_compact_workflow(workflow),
        "support_map": build_support_map(workflow),
    }


def _generate_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    workflow_path = Path(args.workflow)
    output_path = Path(args.output)
    if output_path.resolve() == workflow_path.resolve():
        raise ValueError("Generated Python must not overwrite the source workflow")
    workflow = XmlWorkflowParser().parse(workflow_path)
    if args.answers:
        from alteryx2python.runtime.app_config import prepare_workflow
        workflow = prepare_workflow(workflow, _read_answers(args.answers))
    generated = _write_generated_workflow(workflow, output_path)
    return {
        "command": "generate",
        "status": "ok",
        "workflow": _workflow_summary(workflow),
        "output": str(generated),
        "tool_types": sorted({node.tool_type for node in workflow.nodes}),
        "unsupported_nodes": _unsupported_nodes(workflow),
        "warnings": list(workflow.warnings),
        "representation": "source-xml-and-complete-ir",
        "semantic_equivalence_proven": False,
    }, 0


def _generate_samples_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    sample_root = Path(args.sample_root)
    output_dir = Path(args.output_dir)
    workflow_paths = _workflow_paths(sample_root)
    generated: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    parser = XmlWorkflowParser()

    for workflow_path in workflow_paths:
        try:
            workflow = parser.parse(workflow_path)
            output_path = output_dir / _generated_relative_path(sample_root, workflow_path)
            generated_path = _write_generated_workflow(workflow, output_path)
            generated.append(
                {
                    "source": str(workflow_path),
                    "output": str(generated_path),
                    "workflow": _workflow_summary(workflow),
                    "tool_types": sorted({node.tool_type for node in workflow.nodes}),
                    "unsupported_nodes": _unsupported_nodes(workflow),
                    "warnings": list(workflow.warnings),
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "source": str(workflow_path),
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
            )

    return {
        "command": "generate-samples",
        "status": "ok" if not errors else "partial",
        "sample_root": str(sample_root),
        "output_dir": str(output_dir),
        "workflow_count": len(workflow_paths),
        "generated_count": len(generated),
        "error_count": len(errors),
        "generated": generated,
        "errors": errors,
        "unsupported_tool_types": _unsupported_tool_type_counts(generated),
    }, 0 if not errors else 1


def _run_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    workflow = XmlWorkflowParser().parse(Path(args.workflow))
    context = WorkflowContext(runtime_config={"answers": _read_answers(args.answers)} if args.answers else {"skip_app_configuration": True} if args.data_slice else None)
    try:
        overrides = _apply_output_overrides(workflow, args.override_output)
        result = run_workflow_graph(workflow, context, target_node_ids={str(args.target_node)})
    except Exception as exc:
        return _command_error_report(
            command="run",
            exc=exc,
            workflow=workflow,
            target_node=str(args.target_node),
            output_overrides=_parse_raw_overrides(args.override_output),
            context=context,
        ), 2
    report = {
        "command": "run",
        "status": "ok",
        "workflow": _workflow_summary(workflow),
        "target_node": str(args.target_node),
        "execution_order": list(result.execution_order),
        "skipped_node_ids": list(result.skipped_node_ids),
        "warnings": list(result.warnings),
        "context_warnings": list(context.warnings),
        "context_errors": list(context.errors),
        "diagnostics": list(context.diagnostics),
        "output_overrides": overrides,
        "outputs": _result_outputs(result),
        "contract_evidence": _result_contract_evidence(result),
        "runtime_result": result.to_dict(),
        "trace": context.execution_report(),
    }
    return report, 0


def _compare_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    report = _compare_paths(Path(args.actual), Path(args.expected), args.mode)
    report["command"] = "compare"
    return report, 0 if report["matches"] else 1


def _certify_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    workflow = XmlWorkflowParser().parse(Path(args.workflow))
    context = WorkflowContext()
    try:
        overrides = _apply_output_overrides(workflow, args.override_output)
        result = run_workflow_graph(workflow, context, target_node_ids={str(args.target_node)})
        certification_issues = certification_issues_for_nodes(workflow, result.execution_order)

        actual_path = Path(args.actual) if args.actual else _single_output_path(overrides)
        compare_report = _compare_paths(actual_path, Path(args.expect), args.compare)
    except Exception as exc:
        return _command_error_report(
            command="certify",
            exc=exc,
            workflow=workflow,
            target_node=str(args.target_node),
            output_overrides=_parse_raw_overrides(args.override_output),
            context=context,
        ), 2
    status = "certified" if not certification_issues and compare_report["matches"] else "failed"
    report = {
        "command": "certify",
        "status": status,
        "workflow": _workflow_summary(workflow),
        "target_node": str(args.target_node),
        "execution_order": list(result.execution_order),
        "skipped_node_ids": list(result.skipped_node_ids),
        "warnings": list(result.warnings),
        "context_warnings": list(context.warnings),
        "context_errors": list(context.errors),
        "diagnostics": list(context.diagnostics),
        "output_overrides": overrides,
        "certification_issues": certification_issues,
        "compare": compare_report,
        "contract_evidence": _result_contract_evidence(result),
        "runtime_result": result.to_dict(),
        "trace": context.execution_report(),
    }
    return report, 0 if status == "certified" else 1


def _apply_output_overrides(workflow: Any, raw_overrides: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    nodes_by_id = {node.node_id: node for node in workflow.nodes}
    for raw_override in raw_overrides:
        if "=" not in raw_override:
            raise ValueError("--override-output must use NODE_ID=PATH")
        node_id, path = raw_override.split("=", 1)
        node = nodes_by_id.get(node_id)
        if node is None:
            raise ValueError(f"Override references unknown node: {node_id}")
        normalized = node.config.get("normalized", {})
        if not isinstance(normalized, dict):
            normalized = {}
        node.config["normalized"] = {**normalized, "file": path}
        overrides[node_id] = path
    return overrides


def _parse_raw_overrides(raw_overrides: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for raw_override in raw_overrides:
        if "=" not in raw_override:
            overrides[raw_override] = ""
            continue
        node_id, path = raw_override.split("=", 1)
        overrides[node_id] = path
    return overrides


def _single_output_path(overrides: dict[str, str]) -> Path:
    if len(overrides) != 1:
        raise ValueError("--actual is required when there is not exactly one --override-output")
    return Path(next(iter(overrides.values())))


def _compare_paths(actual_path: Path, expected_path: Path, mode: str) -> dict[str, Any]:
    if mode == "bytes":
        actual_bytes = actual_path.read_bytes()
        expected_bytes = expected_path.read_bytes()
        return {
            "mode": "bytes",
            "status": "match" if actual_bytes == expected_bytes else "mismatch",
            "matches": actual_bytes == expected_bytes,
            "actual": str(actual_path),
            "expected": str(expected_path),
            "actual_size": len(actual_bytes),
            "expected_size": len(expected_bytes),
            "first_difference": _first_byte_difference(actual_bytes, expected_bytes),
        }
    actual = pd.read_csv(actual_path, dtype=object, keep_default_na=False)
    expected = pd.read_csv(expected_path, dtype=object, keep_default_na=False)
    diff = compare_dataframes(actual, expected)
    return {
        "mode": "csv",
        "status": "match" if diff.matches else "mismatch",
        "matches": diff.matches,
        "actual": str(actual_path),
        "expected": str(expected_path),
        "actual_shape": [len(actual.index), len(actual.columns)],
        "expected_shape": [len(expected.index), len(expected.columns)],
        "diff": diff.to_dict(),
    }


def _generate_workflow_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from alteryx2python.workflow_presets import preset_names, render_preset

    if args.spec:
        from alteryx2python.workflow_spec import load_workflow_spec
        spec = load_workflow_spec(args.spec)
        output = Path(args.output)
        if args.python_output and Path(args.python_output).resolve() == output.resolve():
            raise ValueError("Native workflow and Python output require different paths")
        if output.suffix.lower() != "." + spec.kind:
            raise ValueError("Output suffix must agree with graph kind")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(spec.to_xml(), encoding="utf-8")
        parsed = XmlWorkflowParser().parse(output)
        if args.python_output:
            _write_generated_workflow(parsed, Path(args.python_output))
        return {"command": "generate-workflow", "status": "ok", "workflow": str(output),
                "nodes": len(parsed.nodes), "edges": len(parsed.edges), "python_output": args.python_output,
                "unsupported_nodes": _unsupported_nodes(parsed), "native_semantics_proven": False}, 0
    presets = preset_names()
    if args.preset not in presets:
        return {"command": "generate-workflow", "status": "error", "error": f"unknown preset {args.preset!r}; available: {presets}"}, 2
    output = Path(args.output)
    if args.python_output and Path(args.python_output).resolve() == output.resolve():
        raise ValueError("Native workflow and Python output require different paths")
    csv_out = Path(args.csv_out).resolve() if args.csv_out else output.resolve().with_name(output.stem + "_native.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    xml = render_preset(args.preset, str(csv_out), seed=args.seed, rows=args.rows)
    output.write_text(xml, encoding="utf-8")
    parsed = XmlWorkflowParser().parse(output)
    if args.python_output:
        _write_generated_workflow(parsed, Path(args.python_output))
    return {
        "command": "generate-workflow",
        "status": "ok",
        "preset": args.preset,
        "workflow": str(output),
        "csv_out": str(csv_out),
        "seed": args.seed,
        "rows": args.rows,
        "nodes": len(parsed.nodes),
        "edges": len(parsed.edges),
        "tool_types": sorted({node.tool_type for node in parsed.nodes}),
    }, 0


def _run_native_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    workflow = Path(args.workflow)
    if args.watch_file:
        watch_file = Path(args.watch_file)
    else:
        parsed = XmlWorkflowParser().parse(workflow)
        sinks = [node for node in parsed.nodes if node.tool_type == "DbFileOutput"]
        if len(sinks) != 1:
            raise ValueError("--watch-file is required when the workflow has multiple or no file outputs")
        from alteryx2python.tools.dbfileoutput import _resolve_path
        config = sinks[0].config.get("normalized", {})
        watch_file = _resolve_path(str(config.get("file", "")).split("|||", 1)[0], config.get("base_dir"))
    result = run_native(workflow, watch_file, runner=args.runner, timeout=args.timeout)
    return {
        "command": "run-native",
        "status": "ok" if result.ok else result.status,
        "runner": result.runner,
        "detail": result.detail,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "watch_file": str(watch_file),
        "output_exists": watch_file.exists(),
    }, 0 if result.ok else 1


def _equivalence_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    workflow = Path(args.workflow)
    if args.per_node:
        if not args.output_dir:
            raise ValueError("--per-node requires --output-dir for immutable native evidence")
        from alteryx2python.equivalence import run_node_equivalence
        report = run_node_equivalence(workflow, Path(args.output_dir), Path(args.engine) if args.engine else None, args.timeout)
        report["command"] = "equivalence"
        return report, 0 if report["status"] == "match" else 1 if report["status"] == "mismatch" else 2
    report = run_equivalence(
        workflow,
        native_csv=Path(args.native_csv) if args.native_csv else None,
        oracle_csv=Path(args.oracle) if args.oracle else None,
        runner=args.runner,
        timeout=args.timeout,
    )
    report["command"] = "equivalence"
    exit_code = 0 if report.get("equivalent") is True else (1 if report.get("equivalent") is False else 2)
    return report, exit_code


def _equivalence_suite_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    presets = [name.strip() for name in args.presets.split(",")] if args.presets else None
    report = run_equivalence_suite(
        Path(args.out_dir),
        presets=presets,
        seed=args.seed,
        rows=args.rows,
        runner=args.runner,
    )
    report["command"] = "equivalence-suite"
    summary = report["summary"]
    exit_code = 1 if summary["mismatched"] else 2 if summary["native_blocked"] else 0
    return report, exit_code


def _read_answers(path):
    answers = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(answers, dict):
        raise ValueError("Answers file must contain a JSON object keyed by question name or node ID")
    return answers


def _tools_command(args):
    from alteryx2python.parity.coverage import coverage_report
    report = coverage_report(json.loads((Path(__file__).parent.parent / "docs/tools/official_inventory.json").read_text(encoding="utf-8")))
    if args.tool:
        report["tools"] = [item for item in report["tools"] if args.tool in {item["tool_type"], item["plugin_id"], item["name"]}]
        if not report["tools"]:
            raise ValueError(f"Unknown official tool: {args.tool}")
    for item in report["tools"]:
        metadata = TOOL_REGISTRY._registry.get(item["tool_type"])
        item["declared_input_anchors"] = list(metadata.input_anchors) if metadata else None
        item["declared_output_anchors"] = list(metadata.output_anchors) if metadata else None
    if args.output:
        _write_json_file(Path(args.output), report)
    return {"command": "tools", **report}, 0


def _write_json_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _workflow_export_command(args):
    from alteryx2python.workflow_spec import load_workflow_spec
    spec = load_workflow_spec(args.workflow)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(spec.to_json() + "\n", encoding="utf-8")
    return {"command": "workflow-export", "status": "ok", "output": str(output)}, 0


def _connection_spec(value):
    from alteryx2python.workflow_spec import EdgeSpec
    try:
        source, target = value.split("=", 1)
        a, out = source.split(":", 1)
        b, inp = target.split(":", 1)
    except ValueError as exc:
        raise ValueError("Connection must use ID:ANCHOR=ID:ANCHOR") from exc
    return EdgeSpec(a, b, out, inp, inp in {"Action", "Question", "Q", "Condition"})


def _workflow_edit_command(args):
    from alteryx2python.workflow_spec import NodeSpec, load_workflow_spec
    spec = load_workflow_spec(args.workflow)
    removed = set(args.remove_node)
    if removed - {node.node_id for node in spec.nodes}:
        raise ValueError("--remove-node references an unknown top-level node")
    spec.nodes = [node for node in spec.nodes if node.node_id not in removed]
    spec.edges = [edge for edge in spec.edges if edge.source not in removed and edge.target not in removed]
    for path in args.add_node:
        node = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        node["node_id"] = str(node["node_id"])
        spec.nodes.append(NodeSpec(**node))
    for value in args.disconnect:
        edge = _connection_spec(value)
        before = len(spec.edges)
        spec.edges = [current for current in spec.edges if (current.source, current.target, current.source_anchor, current.target_anchor) != (edge.source, edge.target, edge.source_anchor, edge.target_anchor)]
        if before == len(spec.edges):
            raise ValueError(f"Connection to disconnect does not exist: {value}")
    spec.edges.extend(_connection_spec(value) for value in args.connect)
    rendered = spec.to_xml()  # Validate before writing a destination.
    output = Path(args.output)
    if output.suffix.lower() != "." + spec.kind:
        raise ValueError("Output suffix must agree with graph kind")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return {"command": "workflow-edit", "status": "ok", "output": str(output), "nodes": len(spec.nodes), "edges": len(spec.edges)}, 0


def _node_template_command(args):
    from dataclasses import asdict
    from xml.etree import ElementTree as ET
    from alteryx2python.workflow_spec import NodeSpec
    workflow = XmlWorkflowParser().parse(Path(args.workflow))
    node = next((n for n in workflow.nodes if n.node_id == str(args.node)), None)
    if node is None:
        raise ValueError("Unknown node ID")
    element = next(n for n in ET.fromstring(workflow.source_xml).iter("Node") if n.get("ToolID") == node.node_id)
    template = NodeSpec(str(args.new_id) if args.new_id else node.node_id, node.tool_type, template_xml=ET.tostring(element, encoding="unicode"), source_dir=str(Path(args.workflow).resolve().parent))
    _write_json_file(Path(args.output), asdict(template))
    return {"command": "node-template", "status": "ok", "output": args.output, "tool_type": node.tool_type}, 0


def _validate_workflow_command(args):
    from alteryx2python.workflow_spec import load_workflow_spec
    spec = load_workflow_spec(args.workflow)
    workflow = XmlWorkflowParser().parse_xml(spec.to_xml(), Path(args.workflow))
    unsupported = _unsupported_nodes(workflow)
    return {"command": "validate-workflow", "status": "blocked" if args.require_executable and unsupported else "ok",
            "graph_valid": True, "native_semantics_proven": False, "unsupported_nodes": unsupported,
            "warnings": workflow.warnings}, 2 if args.require_executable and unsupported else 0


def _questions_command(args):
    from dataclasses import asdict
    from alteryx2python.runtime.app_config import list_questions
    return {"command": "questions", "status": "ok", "questions": [asdict(q) for q in list_questions(Path(args.workflow))]}, 0


def _configure_workflow_command(args):
    from xml.etree import ElementTree as ET
    from alteryx2python.runtime.app_config import configure_workflow, compile_workflow
    from alteryx2python.parity.manual import _native_review_copy
    import tempfile
    with tempfile.TemporaryDirectory(prefix="a2p-config-") as directory:
        temporary = Path(directory) / "resolved.yxmd"
        rewrites = _native_review_copy(Path(args.workflow).resolve(), temporary)
        if args.defaults_only:
            configured, values = configure_workflow(temporary, _read_answers(args.answers), apply=False)
        else:
            configured, values = compile_workflow(temporary, _read_answers(args.answers))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(configured).write(output, encoding="utf-8", xml_declaration=True)
    return {"command": "configure-workflow", "status": "ok", "output": str(output), "bound_questions": list(values),
            "configuration_mode": "defaults-only" if args.defaults_only else "compiled-data-graph", "path_rewrites": rewrites}, 0


def _run_python_command(args):
    from alteryx2python.parity.manual import export_review_results
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    workflow = XmlWorkflowParser().parse(Path(args.workflow))
    runtime = {"answers": _read_answers(args.answers)} if args.answers else None
    result = export_review_results(workflow, output, runtime_config=runtime)
    return {"command": "run-python", "status": result["status"], "failure": result["failure"],
            "output_dir": str(output), "nodes": len(result["nodes"])}, 0 if result["status"] == "success" else 2


def _proof_suite_command(args):
    from alteryx2python.proof_suite import run_proof_suite
    report = run_proof_suite(Path(args.cases), Path(args.out_dir), engine=Path(args.engine) if args.engine else None, timeout=args.timeout)
    summary = report["summary"]
    return {"command": "proof-suite", **report}, 1 if summary["mismatch"] else 2 if summary["blocked"] or summary["incomplete"] else 0


def _first_byte_difference(actual: bytes, expected: bytes) -> dict[str, Any] | None:
    for index, (actual_byte, expected_byte) in enumerate(zip(actual, expected)):
        if actual_byte != expected_byte:
            return {"index": index, "actual": actual_byte, "expected": expected_byte}
    if len(actual) != len(expected):
        return {"index": min(len(actual), len(expected)), "actual": None, "expected": None}
    return None


def _workflow_summary(workflow: Any) -> dict[str, Any]:
    return {
        "workflow_id": workflow.workflow_id,
        "workflow_name": workflow.workflow_name,
        "source_file": workflow.source_file,
        "node_count": len(workflow.nodes),
        "edge_count": len(workflow.edges),
        "classification": workflow.classification,
    }


def _workflow_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted([*path.rglob("*.yxmd"), *path.rglob("*.yxwz"), *path.rglob("*.yxmc")])


def _generated_relative_path(sample_root: Path, workflow_path: Path) -> Path:
    if sample_root.is_file():
        relative = Path(workflow_path.name)
    else:
        relative = workflow_path.relative_to(sample_root)
    return relative.with_suffix(".py")


def _write_generated_workflow(workflow: Any, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    code = PythonGenerator().generate(workflow)
    output_path.write_text(code + "\n", encoding="utf-8")
    return output_path


def _unsupported_nodes(workflow: Any) -> list[dict[str, Any]]:
    registered = set(TOOL_REGISTRY.list_tool_types())
    return [_node_summary(node) for node in workflow.nodes if not node.tool_type.startswith("Macro_") and
            (node.tool_type not in registered or TOOL_REGISTRY.get(node.tool_type).execution_profile == "unavailable")]


def _unsupported_tool_type_counts(generated: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in generated:
        for node in item["unsupported_nodes"]:
            tool_type = str(node["tool_type"])
            counts[tool_type] = counts.get(tool_type, 0) + 1
    return dict(sorted(counts.items(), key=lambda entry: (-entry[1], entry[0])))


def _node_summary(node: Any) -> dict[str, Any]:
    return {
        "node_id": node.node_id,
        "tool_type": node.tool_type,
        "tool_name": node.tool_name,
        "supported_status": node.supported_status,
        "input_anchors": [anchor.name for anchor in node.input_anchors],
        "output_anchors": [anchor.name for anchor in node.output_anchors],
    }


def _result_outputs(result: Any) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for node_id, node_result in result.node_results.items():
        outputs[node_id] = {
            anchor: {
                "row_count": len(frame.index),
                "columns": [str(column) for column in frame.columns],
            }
            for anchor, frame in node_result.outputs.items()
        }
    return outputs


def _result_contract_evidence(result: Any) -> dict[str, Any]:
    return {
        node_id: node_result.contract_evidence.to_dict()
        for node_id, node_result in result.node_results.items()
        if node_result.contract_evidence is not None
    }


def _error_report(command: str | None, exc: Exception) -> dict[str, Any]:
    return {
        "command": command or "unknown",
        "status": "error",
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc().splitlines(),
        },
    }


def _command_error_report(
    *,
    command: str,
    exc: Exception,
    workflow: Any,
    target_node: str,
    output_overrides: dict[str, str],
    context: WorkflowContext,
) -> dict[str, Any]:
    return {
        **_error_report(command, exc),
        "workflow": _workflow_summary(workflow),
        "target_node": target_node,
        "output_overrides": output_overrides,
        "context_warnings": list(context.warnings),
        "context_errors": list(context.errors),
        "diagnostics": list(context.diagnostics),
        "trace": context.execution_report(),
    }


def _readable_command(args):
    from alteryx2python.generator.readable import ReadablePythonGenerator, read_phase_one, workflow_from_dict
    source = Path(args.source)
    if source.suffix.lower() == '.py':
        workflow = read_phase_one(source)
    elif source.suffix.lower() == '.json':
        workflow = workflow_from_dict(json.loads(source.read_text(encoding='utf-8-sig')))
    else:
        workflow = XmlWorkflowParser().parse(source)
    answers = json.loads(Path(args.answers).read_text(encoding='utf-8-sig')) if args.answers else None
    artifact = ReadablePythonGenerator().generate(workflow, answers=answers, delivery_profile=args.delivery_profile)
    paths = artifact.write(args.output)
    return {'status': 'generated', 'phase': 2, 'files': [str(path.resolve()) for path in paths],
            'nodes': len(artifact.manifest['nodes']), 'native_equivalence': 'unverified'}, 0


def _benchmark_command(args):
    from alteryx2python.benchmark import build_benchmark, run_benchmark
    if args.action == 'build':
        source = build_benchmark(args.output, args.data)
        return {'status': 'built', 'source': str(source.resolve())}, 0
    if args.action == 'inventory':
        from alteryx2python.benchmark_inventory import build_inventory
        report = build_inventory(args.output, args.samples, args.source)
        return report, 0 if report['fully_covered'] else 2
    if not args.source:
        raise ValueError('benchmark run requires --source')
    answers = json.loads(Path(args.answers).read_text(encoding='utf-8-sig')) if args.answers else None
    return run_benchmark(args.source, args.output, answers=answers), 0


def _emit_report(report: dict[str, Any], log_path: str | None) -> None:
    payload = json.dumps(report, indent=2, sort_keys=True, default=str)
    print(payload)
    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
