from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

import pandas as pd

from alteryx2python.certification import assert_nodes_certifiable, certification_issues_for_nodes
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

    return parser


def _inspect_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    workflow = XmlWorkflowParser().parse(Path(args.workflow))
    if args.compact:
        return _compact_report(workflow), 0
    unsupported_nodes = []
    for node in workflow.nodes:
        if node.tool_type not in TOOL_REGISTRY.list_tool_types():
            unsupported_nodes.append(_node_summary(node))
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
    workflow = XmlWorkflowParser().parse(workflow_path)
    generated = _write_generated_workflow(workflow, output_path)
    return {
        "command": "generate",
        "status": "ok",
        "workflow": _workflow_summary(workflow),
        "output": str(generated),
        "tool_types": sorted({node.tool_type for node in workflow.nodes}),
        "unsupported_nodes": _unsupported_nodes(workflow),
        "warnings": list(workflow.warnings),
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
    context = WorkflowContext()
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
    return sorted([*path.rglob("*.yxmd"), *path.rglob("*.yxwz")])


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
    return [_node_summary(node) for node in workflow.nodes if node.tool_type not in registered]


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


def _emit_report(report: dict[str, Any], log_path: str | None) -> None:
    payload = json.dumps(report, indent=2, sort_keys=True, default=str)
    print(payload)
    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
