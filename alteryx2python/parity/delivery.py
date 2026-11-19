"""Verify a delivered workflow against native evidence and both generated builds."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PureWindowsPath
from xml.etree import ElementTree as ET
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from alteryx2python.comparison.workbook import first_workbook_difference

from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.generator.readable import ReadablePythonGenerator, read_phase_one
from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.tools.delivery import XLSX_PROFILE
from alteryx2python.workflow_generator import WorkflowBuilder

from .behavior import changed_artifacts
from .local_adapters import project_report_snapshot, workbook_artifacts
from .runner import (
    capture_python, collect_native, compare_runs, file_artifacts, file_hash, prepare,
    sink_digest, verify_manifest, write_json,
)
from .table_reports import write_table_reports
from .checkpoints import checkpoint_policy
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


def _compare_checkpoints(baseline, checkpoints, omitted=()):
    findings = []
    for node_id in sorted(baseline.keys() | checkpoints.keys()):
        node = baseline.get(node_id)
        frames = checkpoints.get(node_id)
        if frames is None and node_id in omitted and node and not node["outputs"] and node["status"] in {"success", "skipped"}:
            findings.append({"node_id": node_id, "status": "match", "omitted_from_transform": True})
            continue
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


def _delivery_artifacts(directory, xlsx_sinks):
    artifacts = file_artifacts(directory)
    for name in xlsx_sinks & artifacts.keys():
        artifacts[name] = sink_digest(directory / name)
    return artifacts


def reusable_arguments(manifest, workflow, answers, output, as_of=None):
    """Bind a reusable script to one replay, outside its generated source."""
    from alteryx2python.runtime.app_config import prepare_workflow
    from alteryx2python.runtime.variables import bind_workflow_variables

    configured = bind_workflow_variables(prepare_workflow(workflow, answers))
    nodes = {node.node_id: node.config.get("normalized", node.config) for node in configured.nodes}
    arguments = {
        parameter["python_name"]: configured.metadata["answers"][parameter["name"]]
        for parameter in manifest["parameters"]
    }
    base = Path(workflow.source_file).parent
    plan = manifest["reusable"]
    for node_id, entry in plan["inputs"].items():
        raw = nodes[node_id]["file"].partition("|||")[0]
        arguments[entry["parameter"]] = str((base / raw).resolve())
    for node_id, entry in plan["outputs"].items():
        filename = PureWindowsPath(nodes[node_id]["file"].partition("|||")[0]).name
        arguments[entry["parameter"]] = str(output / filename)
    if plan["requires_as_of"]:
        if as_of is None:
            raise ValueError("Reusable delivery needs an explicit replay timestamp")
        arguments["as_of"] = as_of
    return arguments


def _standalone_arguments(script, input_dir, output, events, commands, log_args, as_of, bindings=None):
    command = [sys.executable, "-I", str(script)]
    if bindings is not None:
        return command + ["--bindings", str(bindings)]
    return command + [
        "--input-dir", str(input_dir), "--output-dir", str(output), "--event-working-dir", str(events),
        "--command-working-dir", str(output),
        *[part for program in commands for part in ("--allow-command", program)], *log_args,
        *(["--as-of", as_of] if as_of else []),
    ]


def capture_generated_phase_one(workflow, destination, **options):
    script = destination / "phase_one.py"
    script.write_text(PythonGenerator().generate(workflow), encoding="utf-8", newline="")
    return capture_python(
        Path(workflow.source_file), output_directory=destination / "phase-one-output",
        generated_entry=runpy.run_path(str(script))["run_with_context"], **options,
    )


def _workbook_detail(expected, actual):
    if not expected or not actual or expected.suffix.lower() != ".xlsx":
        return None
    try:
        return first_workbook_difference(expected, actual)
    except (OSError, ValueError, BadZipFile, InvalidFileException) as error:
        return {"dimension": "unreadable_workbook", "reason": str(error)}


def _describe_native_artifacts(findings, manifest, native_directory, phase_one_directory, first, sink_names):
    render_folders = manifest.get("render_folders") or {}
    for item in findings:
        key = item["key"]
        expected = actual = None
        if item["group"] == "sink_artifacts":
            item.update(node_id=key, filename=sink_names.get(key, key))
            if native_name := manifest.get("sink_files", {}).get(key):
                expected = native_directory / native_name
                actual = next(phase_one_directory.glob(f"python-sink-*-{key}{expected.suffix}"), None)
        elif item["group"] == "render_digests":
            node = next(iter(render_folders), None)
            item.update(node_id=node, filename=key)
            if node is not None:
                expected = native_directory / render_folders[node] / key
                name = first.get("render_output_names", {}).get(key, key)
                actual = phase_one_directory / "render" / name
                if name != key:
                    item["phase_one_filename"] = name
        else:
            item["filename"] = key
        if item["status"] != "unexpected" and expected and expected.is_file():
            item["designer_file"] = expected.relative_to(native_directory).as_posix()
        if item["status"] != "missing" and actual and actual.is_file():
            item["phase_one_file"] = actual.relative_to(phase_one_directory).as_posix()
        if item["status"] == "different" and (detail := _workbook_detail(expected, actual)):
            item["detail"] = detail


def verify_delivery(native_directory: Path, destination: Path, *, timeout: float = 120, observable: bool = False,
                    table_selection: tuple[str | None, str | None] | None = None) -> dict:
    native_directory, destination = native_directory.resolve(), destination.resolve()
    manifest = verify_manifest(native_directory)
    source = Path(manifest["source"])
    workflow = XmlWorkflowParser().parse(source)
    answers = manifest.get("answers")
    commands = tuple(manifest.get("event_commands_sha256", {}))
    log_event_ids = manifest.get("log_event_ids", [])
    render_folders = manifest.get("render_folders")
    as_of = manifest.get("as_of") or datetime.now().isoformat(sep=" ", timespec="seconds")
    if render_folders:
        observable = True
    # Scope this proof to sinks whose output locations the capture manifest can identify.
    sink_names = {
        node.node_id: PureWindowsPath(node.config["normalized"]["file"].split("|||", 1)[0]).name
        for node in workflow.nodes if node.node_id in manifest.get("sink_files", {})
    }
    if len(set(sink_names.values())) != len(sink_names):
        raise ValueError("Delivery verification requires distinct output filenames")
    xlsx_sinks = {name for name in sink_names.values() if Path(name).suffix.lower() == ".xlsx"}

    destination.mkdir(parents=True, exist_ok=False)
    phase_one = destination / "phase_one.py"
    first = capture_generated_phase_one(workflow, destination, answers=answers, event_commands=commands,
                                        log_event_ids=log_event_ids, render_folders=render_folders, as_of=as_of)
    report_snapshots = {}
    if render_folders:
        for node_id in manifest["report_projection_nodes"]:
            node = first["nodes"].get(node_id)
            if node is not None:
                for direction in ("inputs", "outputs"):
                    if table_selection is not None:
                        report_snapshots.update({(node_id, direction, anchor): snapshot
                                                 for anchor, snapshot in node[direction].items()})
                    node[direction] = {anchor: project_report_snapshot(snapshot)
                                       for anchor, snapshot in node[direction].items()}
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
    native = collect_native(native_directory, manual=True, capture_report_fields=table_selection is not None)
    native_result = compare_runs(native, first, align_checkpoints=table_selection is not None,
                                 presentation_policy=checkpoint_policy(workflow) if table_selection is not None else None)
    for item in native_result["comparisons"]:
        if item.get("direction") and (table_selection is not None or item["status"] in {"mismatch", "incomplete"}):
            node_id = item["node_id"]
            direction, anchor = item["direction"], item["anchor"]
            files = native["capture_files"].get(node_id, {}).get(direction, {})
            if anchor in files:
                item["designer_file"] = files[anchor]
    _describe_native_artifacts(native_result["artifact_differences"], manifest, native_directory,
                               destination / "phase-one-output", first, sink_names)
    if table_selection is not None:
        try:
            write_table_reports(destination, native, {**first, "report_snapshots": report_snapshots},
                                native_result, table_selection, dynamic_inputs=manifest.get("dynamic_inputs"),
                                probes=manifest["probes"])
        except OSError as error:
            native_result["table_report_issue"] = str(error)
    write_json(destination / "native-vs-phase-one.json", native_result)
    report = {
        "status": "blocked", "source": str(source), "source_sha256": manifest["source_sha256"],
        "answers": answers, "phase_one_sha256": file_hash(phase_one),
        "native_vs_phase_one": native_result["status"], "phase_one_outcome": first["status"],
        "phase_one_vs_phase_two": "pending", "standalone_execution": "pending",
    }
    if log_event_ids:
        report["logging_events"] = logging_evidence
    if render_folders:
        report["render_workbooks"] = {
            "designer": native["render_workbooks"],
            "phase_one": first["workbooks"],
        }
    if as_of:
        report["as_of"] = as_of
    try:
        if first["status"] == "blocked" or (first["status"] != "success" and not observable):
            raise ValueError(f"Generated Phase 1 did not succeed: {first['failure']}")
        phase_one_ir = read_phase_one(phase_one)
        compile_options = {"answers": answers, "log_event_ids": log_event_ids,
                           "delivery_profile": XLSX_PROFILE if render_folders else None}
        try:
            artifact = ReadablePythonGenerator().generate(phase_one_ir, parameter_mode="reusable", **compile_options)
        except UnsupportedLowering as error:
            report["phase_two_reuse_blocker"] = str(error)
            artifact = ReadablePythonGenerator().generate(phase_one_ir, parameter_mode="specialized", **compile_options)
        report["phase_two_mode"] = artifact.manifest["parameter_mode"]
        delivered = destination / "phase_two.py"
        artifact.write(delivered)
        report["phase_two_sha256"] = file_hash(delivered)
        bindings = None
        delivery_dir = destination / "delivery-output"
        if "reusable" in artifact.manifest:
            bindings = destination / "phase-two-bindings.json"
            write_json(bindings, reusable_arguments(artifact.manifest, workflow, answers, delivery_dir, as_of))
            report["phase_two_bindings"] = str(bindings)
        expected_files = {sink_names[node_id]: digest for node_id, digest in first["sink_artifacts"].items()}
        expected_files.update({f"events/{name}": digest for name, digest in first.get("event_artifacts", {}).items()})
        if observable:
            report.update(_verify_observable(
                delivered, source.parent, destination, commands, timeout, first, expected_files,
                report.get("logging_events"),
                as_of, xlsx_sinks, bindings,
            ))
            checks = (native_result["status"], report["phase_one_vs_phase_two"])
            report["status"] = (checks[0] if checks[0] in {"match", "coarse_match"} and checks[1] == "match"
                                else "mismatch" if "mismatch" in checks else "incomplete")
            write_json(destination / "acceptance.json", report)
            return report
        verification_dir = destination / "phase-two-verification-output"
        verification_events = verification_dir / "events" if commands else verification_dir
        verification_events.mkdir(parents=True)
        namespace = {"__name__": "delivery_verification", "__file__": str(delivered)}
        exec(compile(artifact.verification_source, str(delivered), "exec"), namespace)
        checkpoints = {}
        verification_arguments = (
            reusable_arguments(artifact.manifest, workflow, answers, verification_dir, as_of)
            if bindings else dict(input_dir=source.parent, output_dir=verification_dir, allowed_commands=commands,
                                  event_working_dir=verification_events, command_working_dir=verification_dir,
                                  as_of=as_of)
        )
        namespace["run_workflow"](**verification_arguments, checkpoints=checkpoints)
        findings = _compare_checkpoints(first["nodes"], checkpoints, artifact.manifest.get("reusable", {}).get("omitted_nodes", ()))
        phase_two_files = _delivery_artifacts(verification_dir, xlsx_sinks)
        phase_two_result = {
            "nodes": findings, "phase_one_files": expected_files, "phase_two_files": phase_two_files,
            "status": "match" if all(item["status"] == "match" for item in findings)
            and expected_files == phase_two_files else "mismatch",
        }
        write_json(destination / "phase-one-vs-phase-two.json", phase_two_result)
        report["phase_one_vs_phase_two"] = phase_two_result["status"]

        delivery_events = delivery_dir / "events" if commands else delivery_dir
        delivery_events.mkdir(parents=True)
        process = subprocess.run(
            _standalone_arguments(delivered, source.parent, delivery_dir, delivery_events, commands, log_args, as_of, bindings),
            capture_output=True, timeout=timeout, cwd=delivery_dir, check=False,
        )
        (destination / "standalone.stdout.txt").write_bytes(process.stdout)
        (destination / "standalone.stderr.txt").write_bytes(process.stderr)
        delivery_files = _delivery_artifacts(delivery_dir, xlsx_sinks)
        logging_match = _match_logging_events(report.get("logging_events"), phase_two_log, first)
        standalone = {
            "returncode": process.returncode, "outputs": delivery_files,
            "status": "match" if process.returncode == 0 and delivery_files
            and delivery_files == phase_two_files and logging_match else "mismatch",
            **({"logging_events": logging_evidence} if log_event_ids else {}),
        }
        write_json(destination / "standalone.json", standalone)
        report["standalone_execution"] = standalone["status"]
        checks = (report["phase_one_vs_phase_two"], report["standalone_execution"])
        status = report["native_vs_phase_one"]
        report["status"] = (status if status in {"match", "coarse_match"} and checks == ("match", "match")
                            else "mismatch" if "mismatch" in (status, *checks) else "incomplete")
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


def _verify_observable(script, input_dir, destination, commands, timeout, first, expected_files,
                       logging_evidence=None, as_of=None, xlsx_sinks=frozenset(), bindings=None):
    output = destination / "delivery-output"
    events = output / "events" if commands else output
    events.mkdir(parents=True)
    phase_two_log = destination / "phase-two-workflow.jsonl"
    log_args = ["--workflow-log", str(phase_two_log)] if logging_evidence else []
    process = subprocess.run(
        _standalone_arguments(script, input_dir, output, events, commands, log_args, as_of, bindings),
        capture_output=True, timeout=timeout, cwd=output, check=False,
    )
    (destination / "standalone.stdout.txt").write_bytes(process.stdout)
    (destination / "standalone.stderr.txt").write_bytes(process.stderr)
    stderr = process.stderr.decode("utf-8", errors="replace").strip().splitlines()
    failure_kind = stderr[-1].partition(":")[0].rsplit(".", 1)[-1] if stderr else None
    observed = _delivery_artifacts(output, xlsx_sinks)
    workbook_result = {}
    file_differences = []
    if "workbooks" in first:
        rendered = {name: digest for name, digest in workbook_artifacts(output).items() if name not in expected_files}
        observed = {name: digest for name, digest in observed.items() if name not in rendered}
        workbook_result = {"phase_one_workbooks": first["workbooks"], "phase_two_workbooks": rendered}
        for name, change in changed_artifacts(first["workbooks"], rendered):
            file_differences.append({
                "filename": name, "status": change,
                "detail": _workbook_detail(destination / "phase-one-output" / "render" / name, output / name)
                if change == "different" else None,
            })
        workbook_match = first["workbooks"] == rendered
        if first["status"] == "success":
            workbook_match = bool(rendered) and workbook_match
    else:
        workbook_match = True
    if first["status"] == "success":
        outcome_matches = process.returncode == 0
        evidence = bool(expected_files or workbook_result)
    else:
        outcome_matches = process.returncode == 1 and failure_kind == first["failure"]["type"]
        evidence = True
    for name, change in changed_artifacts(expected_files, observed):
        file_differences.append({"filename": name, "status": change})
    logging_match = _match_logging_events(logging_evidence, phase_two_log, first)
    status = "mismatch" if not outcome_matches or expected_files != observed or not logging_match or not workbook_match else "match" if evidence else "incomplete"
    result = {
        "profile": "observable", "status": status, "returncode": process.returncode,
        "phase_one_outcome": first["status"], "phase_two_failure_type": failure_kind if process.returncode else None,
        "phase_one_files": expected_files, "phase_two_files": observed,
        "file_differences": file_differences,
        **workbook_result,
        **({"logging_events": logging_evidence} if logging_evidence else {}),
    }
    write_json(destination / "phase-one-vs-phase-two.json", result)
    write_json(destination / "standalone.json", result)
    return {"phase_one_vs_phase_two": status, "standalone_execution": status}
