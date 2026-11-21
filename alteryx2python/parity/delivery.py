"""Verify a delivered workflow against native evidence and both generated builds."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path, PureWindowsPath
import runpy
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from alteryx2python.comparison.workbook import first_workbook_difference
from alteryx2python.generator.package_compiler import ModularPackageGenerator, PackageArtifact
from alteryx2python.generator.parameters import _alternate
from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.generator.readable import ReadablePythonGenerator, read_phase_one
from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.app_config import question_manifest
from alteryx2python.tools.delivery import XLSX_PROFILE
from alteryx2python.workflow_generator import WorkflowBuilder

from .behavior import changed_artifacts
from .checkpoints import checkpoint_policy
from .local_adapters import project_report_snapshot, workbook_artifacts
from .runner import (
    capture_python,
    collect_native,
    compare_runs,
    file_artifacts,
    file_hash,
    prepare,
    sink_digest,
    verify_manifest,
    write_json,
)
from .snapshot import frame_snapshot
from .table_reports import write_table_reports


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


def _build_case_overrides(
    artifact: PackageArtifact,
    *,
    staged_dir: Path,
    staged_input_nodes: dict[str, str],
    answers: dict | None,
) -> dict:
    overrides: dict = {}
    in_overrides: dict = {}
    for node_id, rel_staged in staged_input_nodes.items():
        in_key = artifact.config_spec.input_key_by_node.get(str(node_id))
        if in_key:
            entry = artifact.config_spec.inputs[in_key]
            staged_abs = str((staged_dir / rel_staged.partition("|||")[0]).resolve())
            in_overrides[in_key] = {"path": staged_abs}
            if entry.get("parameter"):
                overrides.setdefault("parameters", {})[entry["parameter"]] = staged_abs
    if in_overrides:
        overrides["inputs"] = in_overrides

    if answers:
        param_overrides = overrides.setdefault("parameters", {})
        for q_name, val in answers.items():
            py_name = artifact.config_spec.python_param_names.get(q_name)
            if py_name and val is not None:
                param_overrides[py_name] = val
    return overrides


def _compile_delivery_package(
    manifest: dict,
    phase_one_path: Path,
    *,
    staged_dir: Path,
    answers: dict | None,
    log_event_ids: list[str],
    delivery_profile: str | None,
    first_capture: dict,
) -> tuple[PackageArtifact, dict]:
    """Compile Phase 2 package from un-staged original workflow whenever available."""
    orig_path = Path(manifest["original_source"]) if manifest.get("original_source") else None
    if orig_path is not None and orig_path.is_file():
        if manifest.get("original_source_sha256") and file_hash(orig_path) != manifest["original_source_sha256"]:
            raise ValueError(f"Original workflow changed after preparation: {orig_path}")
        compile_wf = XmlWorkflowParser().parse(orig_path)
    else:
        compile_wf = read_phase_one(phase_one_path)

    staged_input_nodes = manifest.get("staged_input_nodes") or {}
    generator = ModularPackageGenerator()
    try:
        initial = generator.generate(
            compile_wf,
            parameter_mode="dynamic",
            delivery_profile=delivery_profile,
            log_event_ids=log_event_ids,
        )
        mode_used = "dynamic"
    except UnsupportedLowering:
        initial = generator.generate(
            compile_wf,
            answers=answers,
            parameter_mode="specialized",
            delivery_profile=delivery_profile,
            log_event_ids=log_event_ids,
        )
        mode_used = "specialized"

    case_overrides = _build_case_overrides(
        initial,
        staged_dir=staged_dir,
        staged_input_nodes=staged_input_nodes,
        answers=answers,
    )

    if first_capture.get("status") == "success" and first_capture.get("sink_artifacts") and not delivery_profile:
        artifact = generator.generate(
            compile_wf,
            answers=answers if mode_used == "specialized" else None,
            parameter_mode=mode_used,
            delivery_profile=delivery_profile,
            log_event_ids=log_event_ids,
            reference_capture=first_capture,
            reference_input_dir=staged_dir,
            reference_overrides=case_overrides,
        )
    else:
        artifact = initial
    artifact.manifest["parameter_mode"] = mode_used
    return artifact, case_overrides


def _run_package_subprocess(
    pkg_dir: Path,
    *,
    config_path: Path,
    input_dir: Path,
    output_dir: Path,
    events_dir: Path,
    commands: tuple[str, ...],
    log_args: list[str],
    as_of: str | None,
    timeout: float,
) -> subprocess.CompletedProcess:
    output_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            sys.executable,
            "-I",
            str(pkg_dir),
            "--config",
            str(config_path),
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--event-working-dir",
            str(events_dir),
            "--command-working-dir",
            str(output_dir),
            *[part for command in commands for part in ("--allow-command", command)],
            *log_args,
            *(["--as-of", as_of] if as_of else []),
        ],
        capture_output=True,
        timeout=timeout,
        cwd=output_dir,
        check=False,
    )


def _run_additional_boundary_cases(
    *,
    staged_source: Path,
    pkg_dir: Path,
    artifact: PackageArtifact,
    base_overrides: dict,
    answers: dict | None,
    commands: tuple[str, ...],
    sink_names: dict[str, str],
    xlsx_sinks: set[str],
    as_of: str | None,
    timeout: float,
) -> dict[str, dict]:
    """Verify parameter perturbation and 0-row empty input cases WITHOUT recompiling Phase 2."""
    results: dict[str, dict] = {}
    if artifact.manifest.get("parameter_mode") != "dynamic":
        return results

    if staged_source.suffix.lower() == ".yxwz" and staged_source.is_file():
        questions = question_manifest(ET.fromstring(staged_source.read_bytes()))
        scalar_qs = [
            q for q in questions
            if q.kind not in {"FileBrowse", "QuestionFileBrowse", "FolderBrowse"}
            and q.name in artifact.config_spec.python_param_names
        ]
        if scalar_qs and answers:
            perturbed_answers = dict(answers)
            changed_any = False
            for q in scalar_qs:
                try:
                    alt = _alternate(q, answers[q.name])
                except Exception:
                    continue
                if alt != answers[q.name]:
                    perturbed_answers[q.name] = alt
                    changed_any = True
                    break
            if changed_any:
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_root = Path(tmp)
                    p1_capture = capture_python(
                        staged_source,
                        output_directory=tmp_root / "p1_out",
                        answers=perturbed_answers,
                        event_commands=commands,
                        as_of=as_of,
                    )
                    if p1_capture["status"] == "success":
                        p1_files = {sink_names[nid]: digest for nid, digest in p1_capture["sink_artifacts"].items() if nid in sink_names}
                        pert_overrides = deepcopy(base_overrides)
                        for q_n, val in perturbed_answers.items():
                            py_n = artifact.config_spec.python_param_names.get(q_n)
                            if py_n:
                                pert_overrides.setdefault("parameters", {})[py_n] = val
                        cfg_path = tmp_root / "perturbed_config.json"
                        cfg_path.write_text(json.dumps(pert_overrides), encoding="utf-8")
                        p2_out = tmp_root / "p2_out"
                        proc = _run_package_subprocess(
                            pkg_dir,
                            config_path=cfg_path,
                            input_dir=staged_source.parent,
                            output_dir=p2_out,
                            events_dir=p2_out,
                            commands=commands,
                            log_args=[],
                            as_of=as_of,
                            timeout=timeout,
                        )
                        p2_files = _delivery_artifacts(p2_out, xlsx_sinks)
                        results["parameter_perturbation"] = {
                            "status": "match" if proc.returncode == 0 and p1_files == p2_files else "mismatch",
                            "phase_one_files": p1_files,
                            "phase_two_files": p2_files,
                        }

    csv_inputs = {
        k: v for k, v in artifact.config_spec.inputs.items()
        if v.get("format") == "csv" and v.get("has_header", True)
    }
    if csv_inputs and not commands:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            empty_wf_dir = tmp_root / "wf"
            empty_wf_dir.mkdir()
            wf_tree = ET.parse(staged_source)
            can_empty = True
            empty_overrides = deepcopy(base_overrides)

            for nid, in_key in artifact.config_spec.input_key_by_node.items():
                if in_key not in csv_inputs:
                    continue
                entry = csv_inputs[in_key]
                override_path_str = (base_overrides.get("inputs", {}).get(in_key, {}) or {}).get("path")
                param_key = entry.get("parameter")
                if not override_path_str and param_key:
                    override_path_str = (base_overrides.get("parameters", {}) or {}).get(param_key)
                actual_src = Path(override_path_str) if override_path_str else (staged_source.parent / entry["path"])
                if not actual_src.is_absolute():
                    actual_src = (staged_source.parent / actual_src).resolve()
                if not actual_src.is_file():
                    can_empty = False
                    break
                first_line = actual_src.read_bytes().splitlines(keepends=True)[:1]
                if not first_line:
                    can_empty = False
                    break
                header_file = empty_wf_dir / f"empty_{nid}.csv"
                header_file.write_bytes(first_line[0] if first_line[0].endswith((b"\n", b"\r")) else first_line[0] + b"\n")

                for el in wf_tree.iter("Node"):
                    if el.get("ToolID") == str(nid):
                        f_el = el.find("Properties/Configuration/File")
                        if f_el is not None:
                            f_el.text = str(header_file)
                empty_overrides.setdefault("inputs", {})[in_key] = {"path": str(header_file)}
                if param_key:
                    empty_overrides.setdefault("parameters", {})[param_key] = str(header_file)

            empty_answers = dict(answers) if answers else None
            if empty_answers:
                for q in (question_manifest(wf_tree.getroot()) if staged_source.suffix.lower() == ".yxwz" else []):
                    if q.kind in {"FileBrowse", "QuestionFileBrowse"} and q.name in artifact.config_spec.python_param_names:
                        py_n = artifact.config_spec.python_param_names[q.name]
                        if py_n in empty_overrides.get("parameters", {}):
                            empty_answers[q.name] = empty_overrides["parameters"][py_n]

            if can_empty:
                empty_wf_path = empty_wf_dir / staged_source.name
                wf_tree.write(empty_wf_path, encoding="utf-8", xml_declaration=True)
                p1_empty = capture_python(
                    empty_wf_path,
                    output_directory=tmp_root / "p1_empty",
                    answers=empty_answers,
                    as_of=as_of,
                )
                if p1_empty["status"] == "success":
                    p1_files = {sink_names[nid]: digest for nid, digest in p1_empty["sink_artifacts"].items() if nid in sink_names}
                    cfg_path = tmp_root / "empty_config.json"
                    cfg_path.write_text(json.dumps(empty_overrides), encoding="utf-8")
                    p2_empty = tmp_root / "p2_empty"
                    proc = _run_package_subprocess(
                        pkg_dir,
                        config_path=cfg_path,
                        input_dir=empty_wf_dir,
                        output_dir=p2_empty,
                        events_dir=p2_empty,
                        commands=(),
                        log_args=[],
                        as_of=as_of,
                        timeout=timeout,
                    )
                    p2_files = _delivery_artifacts(p2_empty, xlsx_sinks)
                    results["empty_input"] = {
                        "status": "match" if proc.returncode == 0 and p1_files == p2_files else "mismatch",
                        "phase_one_files": p1_files,
                        "phase_two_files": p2_files,
                    }

    return results


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
        delivery_profile = XLSX_PROFILE if render_folders else None
        compile_options = {"answers": answers, "log_event_ids": log_event_ids, "delivery_profile": delivery_profile}

        # Preserve single-file transform metadata when supported so legacy transform callers stay working
        legacy_artifact = None
        delivered = destination / "phase_two.py"
        bindings = None
        delivery_dir = destination / "delivery-output"
        try:
            try:
                legacy_artifact = ReadablePythonGenerator().generate(phase_one_ir, parameter_mode="reusable", **compile_options)
            except UnsupportedLowering as error:
                report["phase_two_reuse_blocker"] = str(error)
                legacy_artifact = ReadablePythonGenerator().generate(phase_one_ir, parameter_mode="specialized", **compile_options)
            report["phase_two_mode"] = legacy_artifact.manifest["parameter_mode"]
            legacy_artifact.write(delivered)
            report["phase_two_sha256"] = file_hash(delivered)
            if "reusable" in legacy_artifact.manifest:
                bindings = destination / "phase-two-bindings.json"
                write_json(bindings, reusable_arguments(legacy_artifact.manifest, workflow, answers, delivery_dir, as_of))
                report["phase_two_bindings"] = str(bindings)
        except (UnsupportedLowering, NotImplementedError, ValueError):
            legacy_artifact = None

        expected_files = {sink_names[node_id]: digest for node_id, digest in first["sink_artifacts"].items()}
        expected_files.update({f"events/{name}": digest for name, digest in first.get("event_artifacts", {}).items()})

        pkg_artifact = None
        case_overrides = None
        if not manifest.get("dynamic_inputs") and first["status"] == "success":
            try:
                pkg_artifact, case_overrides = _compile_delivery_package(
                    manifest,
                    phase_one,
                    staged_dir=source.parent,
                    answers=answers,
                    log_event_ids=log_event_ids,
                    delivery_profile=delivery_profile,
                    first_capture=first,
                )
            except (UnsupportedLowering, NotImplementedError):
                pkg_artifact = None

        if pkg_artifact is not None and case_overrides is not None:
            pkg_dir = destination / "package"
            pkg_artifact.write(pkg_dir)
            case_config_path = destination / "case_config.json"
            write_json(case_config_path, case_overrides)
            report["phase_two_package"] = str(pkg_dir)
            report["phase_two_sha256"] = pkg_artifact.manifest["generated_sha256"]

            delivery_events = delivery_dir / "events" if commands else delivery_dir
            process = _run_package_subprocess(
                pkg_dir,
                config_path=case_config_path,
                input_dir=source.parent,
                output_dir=delivery_dir,
                events_dir=delivery_events,
                commands=commands,
                log_args=log_args,
                as_of=as_of,
                timeout=timeout,
            )
            (destination / "standalone.stdout.txt").write_bytes(process.stdout)
            (destination / "standalone.stderr.txt").write_bytes(process.stderr)
            stderr_lines = process.stderr.decode("utf-8", errors="replace").strip().splitlines()
            failure_kind = stderr_lines[-1].partition(":")[0].rsplit(".", 1)[-1] if stderr_lines else None
            observed_files = _delivery_artifacts(delivery_dir, xlsx_sinks)

            workbook_result = {}
            file_differences = []
            if "workbooks" in first:
                rendered = {name: digest for name, digest in workbook_artifacts(delivery_dir).items() if name not in expected_files}
                observed_files = {name: digest for name, digest in observed_files.items() if name not in rendered}
                workbook_result = {"phase_one_workbooks": first["workbooks"], "phase_two_workbooks": rendered}
                for name, change in changed_artifacts(first["workbooks"], rendered):
                    file_differences.append({
                        "filename": name, "status": change,
                        "detail": _workbook_detail(destination / "phase-one-output" / "render" / name, delivery_dir / name)
                        if change == "different" else None,
                    })
                workbook_match = bool(rendered) and first["workbooks"] == rendered
            else:
                workbook_match = True

            for name, change in changed_artifacts(expected_files, observed_files):
                file_differences.append({"filename": name, "status": change})

            outcome_matches = process.returncode == 0
            has_evidence = bool(expected_files or workbook_result) or not observable
            logging_match = _match_logging_events(report.get("logging_events"), phase_two_log, first)

            boundary_cases: dict[str, dict] = {}
            if outcome_matches and expected_files == observed_files and workbook_match and not delivery_profile:
                boundary_cases = _run_additional_boundary_cases(
                    staged_source=source,
                    pkg_dir=pkg_dir,
                    artifact=pkg_artifact,
                    base_overrides=case_overrides,
                    answers=answers,
                    commands=commands,
                    sink_names=sink_names,
                    xlsx_sinks=xlsx_sinks,
                    as_of=as_of,
                    timeout=timeout,
                )

            extra_ok = all(item["status"] == "match" for item in boundary_cases.values())
            p2_status = (
                "mismatch"
                if not outcome_matches or expected_files != observed_files or not logging_match or not workbook_match or not extra_ok
                else ("match" if has_evidence else "incomplete")
            )

            if p2_status == "match":
                pkg_artifact.manifest["python_differential"] = "verified"
                (pkg_dir / "manifest.json").write_text(
                    json.dumps(pkg_artifact.manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )

            phase_two_result = {
                "profile": "boundary_package",
                "status": p2_status,
                "returncode": process.returncode,
                "phase_one_outcome": first["status"],
                "phase_two_failure_type": failure_kind if process.returncode else None,
                "phase_one_files": expected_files,
                "phase_two_files": observed_files,
                "file_differences": file_differences,
                "boundary_cases": boundary_cases,
                **workbook_result,
                **({"logging_events": logging_evidence} if log_event_ids else {}),
            }
            write_json(destination / "phase-one-vs-phase-two.json", phase_two_result)
            write_json(destination / "standalone.json", {
                "returncode": process.returncode,
                "outputs": observed_files,
                "status": p2_status,
                **({"logging_events": logging_evidence} if log_event_ids else {}),
            })
            report["phase_one_vs_phase_two"] = p2_status
            report["standalone_execution"] = p2_status
            status = report["native_vs_phase_one"]
            report["status"] = (status if status in {"match", "coarse_match"} and p2_status == "match"
                                else "mismatch" if "mismatch" in (status, p2_status) else "incomplete")
            write_json(destination / "acceptance.json", report)
            return report

        if legacy_artifact is None:
            raise UnsupportedLowering("Workflow could not be compiled by either modular package or legacy Phase 2 compiler")
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
        exec(compile(legacy_artifact.verification_source, str(delivered), "exec"), namespace)
        checkpoints = {}
        verification_arguments = (
            reusable_arguments(legacy_artifact.manifest, workflow, answers, verification_dir, as_of)
            if bindings else dict(input_dir=source.parent, output_dir=verification_dir, allowed_commands=commands,
                                  event_working_dir=verification_events, command_working_dir=verification_dir,
                                  as_of=as_of)
        )
        namespace["run_workflow"](**verification_arguments, checkpoints=checkpoints)
        findings = _compare_checkpoints(first["nodes"], checkpoints, legacy_artifact.manifest.get("reusable", {}).get("omitted_nodes", ()))
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
