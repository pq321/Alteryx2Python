"""Record native Designer outcomes independently of the Python replay."""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.app_config import prepare_workflow
from alteryx2python.runtime.scheduling import container_members, detour_exclusions

from .amp_export import native_probe_path
from .runner import (
    file_artifacts, file_hash, instrumented_path, native_render_artifacts, native_sink_artifacts,
    read_yxdb, write_json,
)


def record_designer_evidence(directory, manifest, receipt, *, receipt_path=None):
    evidence_path = directory / "designer-evidence.json"
    receipt_hash = file_hash(receipt_path) if receipt_path else None
    previous = {}
    if evidence_path.exists():
        previous = json.loads(evidence_path.read_text(encoding="utf-8"))
        if previous.get("designer_receipt_sha256") != receipt_hash:
            raise ValueError("Designer run receipt changed after evidence was recorded")
        for filename, digest in previous["output_sha256"].items():
            if file_hash(directory / filename) != digest:
                raise ValueError("Native output changed after Designer evidence was recorded")
    instrumented = instrumented_path(directory, manifest)
    if not receipt.get("workflow") or Path(receipt["workflow"]).resolve() != instrumented.resolve():
        raise ValueError("Designer run receipt belongs to another workflow")
    status = _outcome(instrumented, manifest, receipt)
    hashes, snapshots, emitted = {}, {}, set()
    expected = {node["node_id"]: set() for node in manifest["nodes"]}
    for probe in manifest["probes"]:
        node_id, anchor = probe["node_id"], probe["anchor"]
        expected[node_id].add(anchor)
        path = directory / probe["file"]
        if not path.is_file():
            continue
        emitted.add(node_id)
        hashes[path.name] = file_hash(path)
        try:
            readable = native_probe_path(path)
            if readable != path:
                hashes[readable.relative_to(directory).as_posix()] = file_hash(readable)
            snapshots[node_id, anchor] = read_yxdb(readable)
        except Exception:
            # The collector reports the unreadable anchor and still compares readable evidence.
            continue
    sinks = native_sink_artifacts(directory, manifest)
    renders = native_render_artifacts(directory, manifest)
    for key, files in (("sink_artifacts", sinks), ("render_artifacts", renders)):
        if key in previous and previous[key] != files:
            raise ValueError("Native delivery artifacts changed after Designer evidence was recorded")
    emitted.update(sinks)
    emitted.update(node for node, folder in manifest.get("render_folders", {}).items() if renders[folder])
    skipped, containers = _skips(manifest, snapshots, expected, emitted, status)
    outcomes = {}
    for node in manifest["nodes"]:
        node_id = node["node_id"]
        if node_id in skipped:
            outcomes[node_id] = "skipped"
        elif expected[node_id]:
            outcomes[node_id] = ("success" if all((node_id, anchor) in snapshots for anchor in expected[node_id])
                                 else "unknown")
        else:
            artifact_node = node_id in manifest.get("sink_files", {}) or node_id in manifest.get("render_folders", {})
            outcomes[node_id] = "success" if node_id in emitted or (status == "success" and not artifact_node) else "unknown"
    evidence = {
        "method": "designer_automation", "status": status, "designer_status": receipt["status"],
        "source_sha256": manifest["source_sha256"], "instrumented_sha256": manifest["instrumented_sha256"],
        "answers": manifest.get("answers"), "output_sha256": hashes,
        "skipped_nodes": sorted(skipped), "node_outcomes": outcomes, "containers": containers,
        **({"designer_receipt_sha256": receipt_hash} if receipt_hash else {}),
        **({"sink_artifacts": sinks} if manifest.get("sink_files") else {}),
        **({"render_artifacts": renders} if manifest.get("render_folders") else {}),
        **({"event_artifacts": file_artifacts(directory / "native-events")} if manifest.get("event_commands_sha256") else {}),
    }
    write_json(evidence_path, evidence)
    return evidence


def _outcome(instrumented, manifest, receipt):
    native_status = receipt["status"]
    if instrumented.suffix.lower() != ".yxwz":
        return "success" if native_status == "outputs_ready" else "incomplete"
    answers = manifest.get("answers") or {}
    if answers and (not receipt.get("finish_clicked") or not _answers_match(answers, receipt)):
        return "incomplete"
    if native_status in {"outputs_ready", "app_failed", "output_timeout"}:
        outcome = receipt.get("app_outcome")
        if outcome in {"success", "failed"}:
            return outcome
        return {"outputs_ready": "success", "app_failed": "failed"}.get(native_status, "incomplete")
    return "incomplete"


def _answers_match(answers, receipt):
    verified = receipt.get("verified_answers") or {}
    if {name: str(value) for name, value in answers.items()} == verified:
        return True
    if receipt.get("answer_review") == "numeric_readback" and len(answers) == 1:
        try:
            return Decimal(next(iter(answers.values()))) == Decimal(receipt.get("app_answer"))
        except (InvalidOperation, TypeError, ValueError):
            return False
    return False


def _skips(manifest, snapshots, expected, emitted, status):
    skipped = {node["node_id"] for node in manifest["nodes"] if node.get("skip_reason")}
    source = Path(manifest["source"])
    if status == "incomplete" and source.suffix.lower() == ".yxwz":
        return skipped - emitted, []
    workflow = prepare_workflow(XmlWorkflowParser().parse(source), manifest.get("answers"))
    nodes = {node.node_id: node for node in workflow.nodes}
    _, detours = detour_exclusions(workflow.nodes, workflow.edges)
    skipped.update(detours - emitted)
    containers = []
    for container in workflow.nodes:
        if container.tool_type not in {"ToolContainer", "ControlContainer"}:
            continue
        members = container_members(container, nodes) & expected.keys()
        if not members:
            continue
        arrivals = sorted({
            edge.target_node_id for edge in workflow.edges
            if edge.target_node_id in members and edge.source_node_id not in members
            and snapshots.get((edge.source_node_id, edge.source_anchor), {}).get("rows")
        })
        disabled = container.config.get("normalized", {}).get("disabled", False)
        observed = sorted(members & emitted)
        if disabled and not observed:
            skipped.update(members)
            status = "disabled"
        elif disabled and observed:
            status = "disabled_but_output_observed"
        elif arrivals and any(expected[node] and node not in emitted for node in arrivals):
            status = "entry_output_unverified"
        else:
            continue
        containers.append({"node_id": container.node_id, "status": status,
                           "entry_nodes_with_input": arrivals, "nodes_with_artifacts": observed})
    return skipped - emitted, containers
