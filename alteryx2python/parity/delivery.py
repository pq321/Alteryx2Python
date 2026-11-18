"""Verify a delivered workflow against native evidence and both generated builds."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path, PureWindowsPath
from xml.etree import ElementTree as ET

from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.generator.readable import ReadablePythonGenerator, read_phase_one
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.workflow_generator import WorkflowBuilder

from .runner import capture_python, collect_native, compare_runs, file_artifacts, file_hash, prepare, verify_manifest, write_json
from .snapshot import frame_snapshot


def prepare_record_id_demo(sample: Path, destination: Path) -> dict:
    tree = ET.parse(sample)
    nodes = tree.getroot().find("Nodes")
    connections = tree.getroot().find("Connections")
    if nodes is None or connections is None or not any(
        node.get("ToolID") == "138" and node.find("GuiSettings") is not None
        and node.find("GuiSettings").get("Plugin", "").endswith(".RecordID.RecordID")
        for node in nodes
    ):
        raise ValueError("Expected the installed Record ID sample with grouped Record ID tool 138")
    builder = WorkflowBuilder()
    builder.add_csv_output("grouped-records.csv")
    sink = ET.fromstring(builder.nodes_xml[-1])
    sink_id = str(max(int(node.get("ToolID")) for node in nodes.iter("Node")) + 1)
    sink.set("ToolID", sink_id)
    nodes.append(sink)
    edge = ET.SubElement(connections, "Connection")
    ET.SubElement(edge, "Origin", ToolID="138", Connection="Output")
    ET.SubElement(edge, "Destination", ToolID=sink_id, Connection="Input")

    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    workflow = destination / "record-id-demo.yxmd"
    tree.write(workflow, encoding="utf-8", xml_declaration=True)
    run_dir = destination / "native"
    prepare(workflow, run_dir)
    entry = {"workflow": str(workflow), "status": "ready", "run_dir": str(run_dir)}
    write_json(destination / "plan.json", [entry])
    return entry


def _compare_checkpoints(baseline, checkpoints):
    findings = []
    for node_id in sorted(baseline.keys() | checkpoints.keys()):
        node = baseline.get(node_id)
        frames = checkpoints.get(node_id)
        if node is None or frames is None:
            findings.append({"node_id": node_id, "status": "missing_node"})
            continue
        expected = node["outputs"]
        # The runtime compatibility return from Output Data is not an Alteryx port.
        observed = {} if node["tool_type"] == "DbFileOutput" else {
            anchor: frame_snapshot(frame) for anchor, frame in frames.items()
        }
        findings.append({
            "node_id": node_id,
            "tool_type": node["tool_type"],
            "anchors": {
                anchor: "match" if expected.get(anchor) == observed.get(anchor) else "mismatch"
                for anchor in sorted(expected.keys() | observed.keys())
            },
            "status": "match" if expected == observed else "mismatch",
        })
    return findings


def verify_delivery(native_directory: Path, destination: Path, *, timeout: float = 120, observable: bool = False) -> dict:
    native_directory, destination = native_directory.resolve(), destination.resolve()
    manifest = verify_manifest(native_directory)
    source = Path(manifest["source"])
    workflow = XmlWorkflowParser().parse(source)
    answers = manifest.get("answers")
    commands = tuple(manifest.get("event_commands_sha256", {}))
    log_event_ids = manifest.get("log_event_ids", [])
    # Scope this proof to sinks whose output locations the capture manifest can identify.
    sink_names = {
        node.node_id: PureWindowsPath(node.config["normalized"]["file"].split("|||", 1)[0]).name
        for node in workflow.nodes if node.node_id in manifest.get("sink_files", {})
    }
    if len(set(sink_names.values())) != len(sink_names):
        raise ValueError("Delivery verification requires distinct output filenames")

    destination.mkdir(parents=True, exist_ok=False)
    phase_one = destination / "phase_one.py"
    phase_one.write_text(PythonGenerator().generate(workflow), encoding="utf-8", newline="")
    first = capture_python(
        source, output_directory=destination / "phase-one-output", answers=answers,
        event_commands=commands, generated_entry=runpy.run_path(str(phase_one))["run_with_context"],
        log_event_ids=log_event_ids,
    )
    write_json(destination / "phase-one-capture.json", first)
    phase_two_log = destination / "phase-two-workflow.jsonl"
    log_args = ["--workflow-log", str(phase_two_log)] if log_event_ids else []
    if log_event_ids:
        phase_one_log = destination / "phase-one-workflow.jsonl"
        phase_one_log.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                        for row in first["workflow_logs"]), encoding="utf-8")
        logging_evidence = {
            "status": "pending", "event_ids": log_event_ids, "native_policy": "excluded_from_designer",
            "phase_one_log": phase_one_log.name, "phase_two_log": phase_two_log.name,
        }
    native = collect_native(native_directory, manual=True)
    native_result = compare_runs(native, first)
    write_json(destination / "native-vs-phase-one.json", native_result)
    report = {
        "status": "blocked", "source": str(source), "source_sha256": manifest["source_sha256"],
        "answers": answers, "phase_one_sha256": file_hash(phase_one),
        "native_vs_phase_one": native_result["status"], "phase_one_outcome": first["status"],
        "phase_one_vs_phase_two": "pending", "standalone_execution": "pending",
    }
    if log_event_ids:
        report["logging_events"] = logging_evidence
    try:
        if first["status"] == "blocked" or (first["status"] != "success" and not observable):
            raise ValueError(f"Generated Phase 1 did not succeed: {first['failure']}")
        artifact = ReadablePythonGenerator().generate(
            read_phase_one(phase_one), answers=answers, parameter_mode="specialized", log_event_ids=log_event_ids,
        )
        delivered = destination / "phase_two.py"
        artifact.write(delivered)
        report["phase_two_sha256"] = file_hash(delivered)
        expected_files = {sink_names[node_id]: digest for node_id, digest in first["sink_artifacts"].items()}
        expected_files.update({f"events/{name}": digest for name, digest in first.get("event_artifacts", {}).items()})
        if observable:
            report.update(_verify_observable(
                delivered, source.parent, destination, commands, timeout, first, expected_files,
                report.get("logging_events"),
            ))
            checks = (native_result["status"], report["phase_one_vs_phase_two"])
            report["status"] = ("match" if checks == ("match", "match")
                                else "mismatch" if "mismatch" in checks else "incomplete")
            write_json(destination / "acceptance.json", report)
            return report
        verification_dir = destination / "phase-two-verification-output"
        verification_events = verification_dir / "events" if commands else verification_dir
        verification_events.mkdir(parents=True)
        namespace = {"__name__": "delivery_verification", "__file__": str(delivered)}
        exec(compile(artifact.verification_source, str(delivered), "exec"), namespace)
        checkpoints = {}
        namespace["run_workflow"](
            input_dir=source.parent, output_dir=verification_dir, allowed_commands=commands,
            event_working_dir=verification_events, command_working_dir=verification_dir,
            checkpoints=checkpoints,
        )
        findings = _compare_checkpoints(first["nodes"], checkpoints)
        phase_two_files = file_artifacts(verification_dir)
        phase_two_result = {
            "nodes": findings, "phase_one_files": expected_files, "phase_two_files": phase_two_files,
            "status": "match" if all(item["status"] == "match" for item in findings)
            and expected_files == phase_two_files else "mismatch",
        }
        write_json(destination / "phase-one-vs-phase-two.json", phase_two_result)
        report["phase_one_vs_phase_two"] = phase_two_result["status"]

        delivery_dir = destination / "delivery-output"
        delivery_events = delivery_dir / "events" if commands else delivery_dir
        delivery_events.mkdir(parents=True)
        process = subprocess.run(
            [sys.executable, "-I", str(delivered), "--input-dir", str(source.parent),
             "--output-dir", str(delivery_dir), "--event-working-dir", str(delivery_events),
             "--command-working-dir", str(delivery_dir),
             *[part for command in commands for part in ("--allow-command", command)], *log_args],
            capture_output=True, timeout=timeout, cwd=delivery_dir, check=False,
        )
        (destination / "standalone.stdout.txt").write_bytes(process.stdout)
        (destination / "standalone.stderr.txt").write_bytes(process.stderr)
        delivery_files = file_artifacts(delivery_dir)
        logging_match = _match_logging_events(report.get("logging_events"), phase_two_log, first)
        standalone = {
            "returncode": process.returncode, "outputs": delivery_files,
            "status": "match" if process.returncode == 0 and delivery_files
            and delivery_files == phase_two_files and logging_match else "mismatch",
            **({"logging_events": logging_evidence} if log_event_ids else {}),
        }
        write_json(destination / "standalone.json", standalone)
        report["standalone_execution"] = standalone["status"]
        report["status"] = "match" if all(
            report[key] == "match" for key in ("native_vs_phase_one", "phase_one_vs_phase_two", "standalone_execution")
        ) else "mismatch" if "mismatch" in report.values() else "incomplete"
    except (ValueError, OSError, RuntimeError, KeyError, subprocess.TimeoutExpired) as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    write_json(destination / "acceptance.json", report)
    return report


def _match_logging_events(evidence, phase_two_log, first):
    if evidence is None:
        return True
    records = [json.loads(line) for line in phase_two_log.read_text(encoding="utf-8").splitlines()] if phase_two_log.is_file() else []
    expected = [(event_id, first["status"]) for event_id in evidence["event_ids"]]
    one = [(row.get("event_id"), row.get("status")) for row in first["workflow_logs"]]
    two = [(row.get("event_id"), row.get("status")) for row in records]
    matched = one == two == expected
    evidence["status"] = "match" if matched else "mismatch"
    return matched


def _verify_observable(script, input_dir, destination, commands, timeout, first, expected_files, logging_evidence=None):
    output = destination / "delivery-output"
    events = output / "events" if commands else output
    events.mkdir(parents=True)
    phase_two_log = destination / "phase-two-workflow.jsonl"
    log_args = ["--workflow-log", str(phase_two_log)] if logging_evidence else []
    process = subprocess.run(
        [sys.executable, "-I", str(script), "--input-dir", str(input_dir), "--output-dir", str(output),
         "--event-working-dir", str(events), "--command-working-dir", str(output),
         *[part for command in commands for part in ("--allow-command", command)], *log_args],
        capture_output=True, timeout=timeout, cwd=output, check=False,
    )
    (destination / "standalone.stdout.txt").write_bytes(process.stdout)
    (destination / "standalone.stderr.txt").write_bytes(process.stderr)
    stderr = process.stderr.decode("utf-8", errors="replace").strip().splitlines()
    failure_kind = stderr[-1].partition(":")[0].rsplit(".", 1)[-1] if stderr else None
    observed = file_artifacts(output)
    if first["status"] == "success":
        outcome_matches = process.returncode == 0
        evidence = bool(expected_files)
    else:
        outcome_matches = process.returncode == 1 and failure_kind == first["failure"]["type"]
        evidence = True
    logging_match = _match_logging_events(logging_evidence, phase_two_log, first)
    status = "mismatch" if not outcome_matches or expected_files != observed or not logging_match else "match" if evidence else "incomplete"
    result = {
        "profile": "observable", "status": status, "returncode": process.returncode,
        "phase_one_outcome": first["status"], "phase_two_failure_type": failure_kind if process.returncode else None,
        "phase_one_files": expected_files, "phase_two_files": observed,
        **({"logging_events": logging_evidence} if logging_evidence else {}),
    }
    write_json(destination / "phase-one-vs-phase-two.json", result)
    write_json(destination / "standalone.json", result)
    return {"phase_one_vs_phase_two": status, "standalone_execution": status}
