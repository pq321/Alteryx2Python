"""Designer/manual review routes that do not require the Engine API feature."""

from __future__ import annotations

import csv
import base64
import json
import shutil
import inspect
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.ir.models import WorkflowIR
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.tools.registry import TOOL_REGISTRY

from .runner import (
    CaptureContext,
    file_hash,
    read_yxdb,
    runtime_hash,
    verify_manifest,
    write_json,
)


def attest_native(
    directory: Path,
    status: str,
    *,
    failed_nodes: list[str] | None = None,
    reviewer: str = "manual",
    note: str = "",
) -> dict[str, Any]:
    """Record the observed Designer outcome; never infer it from Python."""
    if status not in {"success", "failed"}:
        raise ValueError("Native outcome must be success or failed")
    manifest = verify_manifest(directory)
    failures = set(failed_nodes or [])
    ids = {node["node_id"] for node in manifest["nodes"]}
    if not failures <= ids:
        raise ValueError("Failed node is not in the original workflow")
    if (status == "failed") != bool(failures):
        raise ValueError(
            "Failed runs require failed node IDs; successful runs cannot have failed nodes"
        )
    hashes: dict[str, str] = {}
    available: dict[str, set[str]] = {node_id: set() for node_id in ids}
    for probe in manifest["probes"]:
        path = directory / probe["file"]
        if path.exists():
            read_yxdb(path)  # Refuse corrupt/unreadable evidence at confirmation.
            hashes[path.name] = file_hash(path)
            available[probe["node_id"]].add(probe["anchor"])
        elif status == "success":
            raise ValueError(
                f"Successful review is missing native output {probe['file']}"
            )
    outcomes = {}
    for node_id in ids:
        expected = {
            probe["anchor"]
            for probe in manifest["probes"]
            if probe["node_id"] == node_id
        }
        outcomes[node_id] = (
            "failed"
            if node_id in failures
            else "success"
            if expected <= available[node_id] and (expected or status == "success")
            else "not_run"
        )
    review = {
        "status": status,
        "source_sha256": manifest["source_sha256"],
        "instrumented_sha256": manifest["instrumented_sha256"],
        "output_sha256": hashes,
        "node_outcomes": outcomes,
        "reviewer": reviewer,
        "note": note,
        "method": "Designer/manual outcome attestation",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(directory / "manual-review.json", review)
    return review


def _native_review_copy(source: Path, target: Path) -> list[dict[str, str]]:
    """Relocate public file references without changing the data/configuration."""
    tree = ET.parse(source)
    from alteryx2python.parser.file_references import resolve_file_references

    rewrites = resolve_file_references(tree.getroot(), source)
    tree.write(target, encoding="utf-8", xml_declaration=True)
    return rewrites


def _node_support(workflow: WorkflowIR) -> list[dict[str, Any]]:
    nodes = []
    for node in workflow.nodes:
        metadata = TOOL_REGISTRY._registry.get(node.tool_type)
        if metadata is None and node.tool_type.startswith("Macro_"):
            from alteryx2python.tools.macro_engine import execute_static_macro

            function, profile, doc = (
                execute_static_macro,
                "local-static-macro",
                "docs/tools/static_macros.md",
            )
        elif metadata is not None:
            function, profile, doc = (
                inspect.unwrap(metadata.function),
                metadata.execution_profile,
                metadata.semantics_doc,
            )
        else:
            function, profile, doc = None, "unavailable", "docs/tools/unavailable.md"
        nodes.append(
            {
                "node_id": node.node_id,
                "tool_type": node.tool_type,
                "source_plugin": node.tool_name,
                "execution_profile": profile,
                "implementation": f"{function.__module__}.{function.__qualname__}"
                if function
                else None,
                "semantics_doc": doc,
            }
        )
    return nodes


def create_review_bundle(source: Path, destination: Path) -> dict[str, Any]:
    """Export code/checklist without executing the user's workflow on creation."""
    source = source.resolve()
    workflow = XmlWorkflowParser().parse(source)
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source, destination / "original.yxmd")
    native_name = "native-review" + source.suffix
    rewrites = _native_review_copy(source, destination / native_name)
    support = _node_support(workflow)
    write_json(destination / "node-map.json", support)
    (destination / "node-map.md").write_text(
        "# Node to Python mapping\n\n| Node | Alteryx type | Python implementation | Profile |\n| --- | --- | --- | --- |\n"
        + "".join(
            f"| {n['node_id']} | {n['tool_type']} | {n['implementation']} | {n['execution_profile']} |\n"
            for n in support
        ),
        encoding="utf-8",
    )
    write_json(destination / "python-runtime.local.json", {})
    generated = PythonGenerator().generate(workflow, include_main=False)
    generated += '\n\nif __name__ == "__main__":\n'
    generated += "    from pathlib import Path\n    from alteryx2python.parity.manual import export_review_results\n"
    generated += "    import json\n    directory = Path(__file__).resolve().parent\n"
    generated += '    runtime_config = json.loads((directory / "python-runtime.local.json").read_text(encoding="utf-8"))\n'
    generated += "    result = export_review_results(build_workflow(), directory, runtime_config=runtime_config)\n"
    generated += '    print("Python outcome:", result["status"])\n'
    generated += '    print("Review outputs under python-results and fill review.json against Designer.")\n'
    (destination / "workflow.py").write_text(generated, encoding="utf-8")
    manifest = {
        "source": str(source),
        "source_sha256": file_hash(source),
        "generated_sha256": file_hash(destination / "workflow.py"),
        "native_workflow": native_name,
        "native_sha256": file_hash(destination / native_name),
        "path_rewrites": rewrites,
        "nodes": [
            {"node_id": node.node_id, "tool_type": node.tool_type}
            for node in workflow.nodes
        ],
    }
    write_json(destination / "bundle.json", manifest)
    (destination / "README.md").write_text(
        "# Manual Designer/Python review\n\n"
        f"1. Open {native_name} in Designer using File > Open and run. original.yxmd is an unchanged archive.\n"
        "2. From the repository environment, run this bundle's workflow.py. It writes full per-node Python results.\n"
        "3. Inspect each original node/output anchor in Designer and its Python .csv/.json. JSON preserves null/empty/binary.\n"
        "4. In review.json record native_status for every node; for successful outputs set outputs_equal to true/false.\n"
        "5. Run `python -m alteryx2python.parity review-check <bundle-directory>`.\n\n"
        "Matching failures do not require equal exception names/messages. Do not mark pending nodes confirmed.\n"
        "This route records human inspection, not machine-captured native results. To hash and compare native exports automatically use prepare/attest/collect.\n"
        "If you edit the workflow/config/input data, generate a fresh bundle and repeat the run.\n"
        "node-map.md/json identifies each node's actual Python implementation and supported local profile.\n"
        "python-runtime.local.json accepts local runtime configuration (model paths/interpreters); never commit credentials.\n"
        "Relative native file references are made absolute; see bundle.json path_rewrites. Input data must remain unchanged during both runs.\n"
        "CSV uses <NULL> for display only; typed JSON is authoritative when that literal occurs in real strings.\n",
        encoding="utf-8",
    )
    return manifest


def export_review_results(
    workflow: WorkflowIR,
    directory: Path,
    *,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from alteryx2python.runtime.executor import run_workflow_graph

    context = CaptureContext(runtime_config=runtime_config)
    failure = None
    blocked = False
    try:
        graph_result = run_workflow_graph(workflow, context)
        from .snapshot import frame_snapshot

        for node_id, node_result in graph_result.node_results.items():
            context.nodes.setdefault(
                node_id,
                {
                    "tool_type": node_result.tool_type,
                    "status": "success",
                    "inputs": {},
                    "outputs": {
                        anchor: frame_snapshot(frame)
                        for anchor, frame in node_result.outputs.items()
                    },
                },
            )
    except Exception as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        blocked = (
            isinstance(
                exc, (ImportError, NotImplementedError, subprocess.TimeoutExpired)
            )
            or isinstance(exc.__cause__, ImportError)
            or type(exc).__name__ == "SnapshotEncodingError"
        )
    for node in workflow.nodes:
        context.nodes.setdefault(
            node.node_id,
            {
                "tool_type": node.tool_type,
                "status": "not_run",
                "inputs": {},
                "outputs": {},
            },
        )
    out = directory / "python-results"
    out.mkdir(exist_ok=True)
    result = {
        "producer": "python",
        "status": "blocked" if blocked else "failed" if failure else "success",
        "failure": failure,
        "source_sha256": workflow.source_hash,
        "runtime_sha256": runtime_hash(),
        "runtime_config_sha256": file_hash(directory / "python-runtime.local.json")
        if (directory / "python-runtime.local.json").exists()
        else None,
        "nodes": context.nodes,
        "diagnostics": context.diagnostics,
    }
    write_json(out / "capture.json", result)
    checkpoints = []
    for node_id, node in context.nodes.items():
        files = {}
        for index, (anchor, snapshot) in enumerate(node["outputs"].items()):
            # Never interpolate user-supplied anchor names into file paths.
            filename = f"node-{len(checkpoints):04d}-output-{index:02d}"
            write_json(out / (filename + ".json"), snapshot)
            for row_index, row in enumerate(snapshot["rows"]):
                for column_index, cell in enumerate(row):
                    if cell["kind"] == "image":
                        (
                            out / f"{filename}-row-{row_index}-col-{column_index}.png"
                        ).write_bytes(base64.b64decode(cell["png_base64"]))
            with (out / (filename + ".csv")).open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.writer(stream)
                writer.writerow(snapshot["columns"])
                writer.writerows(
                    [_display(cell) for cell in row] for row in snapshot["rows"]
                )
            files[anchor] = f"python-results/{filename}.csv"
        checkpoints.append(
            {
                "node_id": node_id,
                "tool_type": node["tool_type"],
                "python_status": node["status"],
                "native_status": "pending",
                "outputs_equal": None,
                "output_files": files,
                "note": "",
            }
        )
    review = {
        "source_sha256": workflow.source_hash,
        "runtime_sha256": runtime_hash(),
        "capture_sha256": file_hash(out / "capture.json"),
        "runtime_config_sha256": result["runtime_config_sha256"],
        "native_status": "pending",
        "nodes": checkpoints,
    }
    template = directory / "review.json"
    if template.exists():
        # Preserve human work; reruns require an explicit new review of the new capture.
        template = directory / "review-next.json"
    write_json(template, review)
    return result


def _display(cell: dict[str, Any]) -> str:
    if cell["kind"] == "null":
        return "<NULL>"
    if cell["kind"] == "float":
        return str(float.fromhex(cell["value"])) if cell["value"] != "nan" else "NaN"
    if cell["kind"] == "image":
        return f"<Image {cell['width']}x{cell['height']} {cell['mode']}>"
    return str(cell.get("value", ""))


def check_review_bundle(directory: Path) -> dict[str, Any]:
    bundle = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))
    capture_path = directory / "python-results/capture.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    review = json.loads((directory / "review.json").read_text(encoding="utf-8"))
    issues, pending = [], []
    if file_hash(directory / "original.yxmd") != bundle["source_sha256"]:
        issues.append("source_changed")
    if file_hash(directory / "workflow.py") != bundle["generated_sha256"]:
        issues.append("generated_code_changed")
    if file_hash(directory / bundle["native_workflow"]) != bundle["native_sha256"]:
        issues.append("native_workflow_changed")
    if capture.get("runtime_config_sha256") != file_hash(
        directory / "python-runtime.local.json"
    ):
        issues.append("runtime_config_changed")
    if (
        review["capture_sha256"] != file_hash(capture_path)
        or review["runtime_sha256"] != runtime_hash()
    ):
        issues.append("review_or_runtime_stale")
    if (
        review["source_sha256"] != bundle["source_sha256"]
        or capture["source_sha256"] != bundle["source_sha256"]
    ):
        issues.append("review_source_mismatch")
    native = review.get("native_status")
    if native not in {"success", "failed"}:
        pending.append("workflow_outcome_pending")
    elif native != capture["status"]:
        issues.append("workflow_outcome_mismatch")
    reviewed = {node["node_id"]: node for node in review["nodes"]}
    if len(reviewed) != len(review["nodes"]) or set(reviewed) != set(capture["nodes"]):
        issues.append("review_node_set_mismatch")
    for node_id, node in capture["nodes"].items():
        observation = reviewed.get(node_id)
        if observation is None or observation.get("native_status") not in {
            "success",
            "failed",
            "not_run",
        }:
            pending.append(f"node_{node_id}_pending")
        elif observation["native_status"] != node["status"]:
            issues.append(f"node_{node_id}_outcome_mismatch")
        elif node["status"] == "success" and node["outputs"]:
            if observation.get("outputs_equal") is False:
                issues.append(f"node_{node_id}_outputs_differ")
            elif observation.get("outputs_equal") is not True:
                pending.append(f"node_{node_id}_outputs_pending")
    status = (
        "blocked"
        if capture["status"] == "blocked"
        else "mismatch"
        if issues
        else "incomplete"
        if pending
        else "match"
    )
    result = {
        "status": status,
        "profile": "behavioral",
        "evidence_method": "human_review",
        "issues": issues,
        "pending": pending,
        "universal_equivalence_proven": False,
    }
    write_json(directory / "review-result.json", result)
    return result
