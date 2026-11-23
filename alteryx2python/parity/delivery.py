"""Verify a delivered workflow against native evidence and the Phase 2 package."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import re
from pathlib import Path, PureWindowsPath
from shutil import copyfile
import subprocess
import sys
import tempfile
from time import perf_counter
from xml.etree import ElementTree as ET
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from alteryx2python.comparison.workbook import first_workbook_difference
from alteryx2python.expressions.errors import ExpressionError
from alteryx2python.generator.package_compiler import ModularPackageGenerator, PackageArtifact
from alteryx2python.generator.parameters import _alternate
from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.generator.readable import read_phase_one
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


def _delivery_artifacts(directory, xlsx_sinks):
    artifacts = file_artifacts(directory)
    for name in xlsx_sinks & artifacts.keys():
        artifacts[name] = sink_digest(directory / name)
    return artifacts


def capture_generated_phase_one(workflow, destination, **options):
    script = destination / "phase_one.py"
    script.write_text(PythonGenerator().generate(workflow), encoding="utf-8", newline="")
    frozen = read_phase_one(script)
    return capture_python(Path(frozen.source_file), workflow=frozen,
                          output_directory=destination / "phase-one-output", **options)


def _load_phase_one(manifest, staged_source, script):
    if filename := manifest.get("phase_one_file"):
        if filename != "phase_one.py":
            raise ValueError("Unexpected Phase 1 artifact filename")
        saved = staged_source.parent / filename
        copyfile(saved, script)
        if file_hash(script) != manifest.get("phase_one_sha256"):
            raise ValueError("Phase 1 artifact changed after preparation")
    else:
        # Older cases saved the original path and hash but have no frozen IR.
        if not manifest.get("original_source") and (
            "staged_input_nodes" in manifest or manifest.get("dynamic_inputs")
            or (staged_source.parent / "migration.json").is_file()
        ):
            raise UnsupportedLowering("Phase 1 requires the original workflow for a legacy staged case")
        original = Path(manifest.get("original_source") or staged_source)
        if not original.is_file():
            raise UnsupportedLowering(f"Phase 1 original workflow is unavailable: {original}")
        parsed = XmlWorkflowParser().parse(original)
        if manifest.get("original_source_sha256") and parsed.source_hash != manifest["original_source_sha256"]:
            raise ValueError(f"Original workflow changed after preparation: {original}")
        script.write_text(PythonGenerator().generate(parsed), encoding="utf-8", newline="")
    workflow = read_phase_one(script)
    if workflow.source_hash != manifest.get("original_source_sha256", manifest["source_sha256"]):
        raise ValueError("Phase 1 IR does not match the workflow recorded at preparation")
    return workflow


def _case_runtime(manifest):
    aliases = {
        str(Path(entry["source"]).resolve()): snapshot
        for snapshot, entry in manifest.get("input_origins", {}).items()
    }
    return {
        "input_path_aliases": aliases,
        "dynamic_input_templates": {
            node_id: dynamic["template"]["snapshot"]
            for node_id, dynamic in manifest.get("dynamic_inputs", {}).items()
        },
    }


def _project_dynamic_probes(native, manifest):
    """Compare original nodes against the Designer graph augmented for file isolation."""
    for node_id, binding in manifest.get("dynamic_inputs", {}).items():
        adapter_id = binding["isolation_tool"]
        adapter = native["nodes"].pop(adapter_id, {})
        node = native["nodes"].get(node_id, {})
        for anchor, origins in native.get("input_sources", {}).get(node_id, {}).items():
            if origins["node_id"] != adapter_id or anchor not in node.get("inputs", {}):
                continue
            snapshot = node["inputs"][anchor]
            field = f"__a2p_path_{node_id}"
            if field in snapshot["columns"]:
                indices = [i for i, column in enumerate(snapshot["columns"]) if column != field]
                node["inputs"][anchor] = {
                    **snapshot,
                    "columns": [snapshot["columns"][i] for i in indices],
                    "rows": [[row[i] for i in indices] for row in snapshot["rows"]],
                    "schema": [entry for entry in (snapshot.get("schema") or []) if entry["name"] != field],
                }
            if source := native.get("input_sources", {}).get(adapter_id, {}).get("Input"):
                native["input_sources"][node_id][anchor] = source
        # A failed isolation adapter prevented the original Dynamic Input from executing.
        if adapter.get("status") == "failed" and node.get("status") in {"unknown", "not_run"}:
            node["status"] = "failed"
        for key in ("missing_native_outputs", "unreadable_native_outputs"):
            if key in native:
                native[key] = [probe for probe in native[key] if probe["node_id"] != adapter_id]


def _workbook_detail(expected, actual, *, allow_excel_roundoff=False):
    if not expected or not actual or expected.suffix.lower() != ".xlsx":
        return None
    try:
        return first_workbook_difference(expected, actual, allow_excel_roundoff=allow_excel_roundoff)
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
            if detail["dimension"] == "cell":
                material = _workbook_detail(expected, actual, allow_excel_roundoff=True)
                if material is None:
                    item.update(status="coarse_match", reason="excel_numeric_roundoff")
                elif material != detail:
                    item["detail"] = material
                    item["first_exact_difference"] = detail


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


def write_phase_two_candidate(workflow, destination: Path, *, phase_one_sha256: str, log_event_ids=()):
    """Compile and save the frozen IR before attempting runtime verification."""
    delivery_profile = XLSX_PROFILE if any(
        node.tool_type == "PortfolioComposerRender" for node in workflow.nodes
    ) else None
    artifact = ModularPackageGenerator().generate(
        workflow, delivery_profile=delivery_profile, log_event_ids=log_event_ids,
    )
    artifact.manifest["phase_one_sha256"] = phase_one_sha256
    artifact.write(destination)
    return artifact


def _delivery_case_config(artifact: PackageArtifact, workflow, manifest: dict, runtime: dict) -> dict:
    staged_dir = Path(manifest["source"]).parent
    original = Path(workflow.source_file)
    overrides = _build_case_overrides(
        artifact, staged_dir=staged_dir,
        staged_input_nodes=manifest.get("staged_input_nodes") or {}, answers=manifest.get("answers"),
    )
    aliases = runtime["input_path_aliases"]
    for node_id, dynamic in manifest.get("dynamic_inputs", {}).items():
        key = f"dynamic_input_{node_id}"
        if key in artifact.config_spec.operations:
            overrides.setdefault("operations", {})[key] = {
                "input_dir": str(original.parent),
                "path_aliases": aliases,
                "schema_reference": dynamic["template"]["snapshot"],
            }
    if aliases:
        overrides.setdefault("runtime", {}).update(
            original_input_dir=str(original.parent), input_aliases=aliases,
        )
    return overrides


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
    verification_paths: tuple[Path, Path] | None = None,
) -> subprocess.CompletedProcess:
    output_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-X",
            "utf8",
            *(
                [str(Path(__file__).with_name("phase_two_verification.py")), str(pkg_dir),
                 *(str(path) for path in verification_paths)]
                if verification_paths else [str(pkg_dir)]
            ),
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
    workflow,
    runtime: dict,
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
        questions = question_manifest(ET.fromstring(workflow.source_xml))
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
                        staged_source, workflow=workflow, runtime_config=runtime,
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
            empty_inputs = {}
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
                with actual_src.open("rb") as stream:
                    first_line = next(iter(stream.readline().splitlines(keepends=True)), b"")
                if not first_line:
                    can_empty = False
                    break
                header_file = empty_wf_dir / f"empty_{nid}.csv"
                header_file.write_bytes(first_line if first_line.endswith((b"\n", b"\r")) else first_line + b"\n")

                empty_inputs[nid] = str(header_file)
                empty_overrides.setdefault("inputs", {})[in_key] = {"path": str(header_file)}
                if param_key:
                    empty_overrides.setdefault("parameters", {})[param_key] = str(header_file)

            empty_answers = dict(answers) if answers else None
            if empty_answers:
                for q in (question_manifest(ET.fromstring(workflow.source_xml)) if staged_source.suffix.lower() == ".yxwz" else []):
                    if q.kind in {"FileBrowse", "QuestionFileBrowse"} and q.name in artifact.config_spec.python_param_names:
                        py_n = artifact.config_spec.python_param_names[q.name]
                        if py_n in empty_overrides.get("parameters", {}):
                            empty_answers[q.name] = empty_overrides["parameters"][py_n]

            if can_empty:
                p1_empty = capture_python(
                    staged_source, workflow=workflow, runtime_config={**runtime, "input_bindings": empty_inputs},
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
                    table_selection: tuple[str | None, str | None] | None = None, _verified_manifest: dict | None = None) -> dict:
    native_directory, destination = native_directory.resolve(), destination.resolve()
    started = perf_counter()
    manifest = verify_manifest(native_directory) if _verified_manifest is None else _verified_manifest
    timings = {"manifest_validation": round(perf_counter() - started, 3)}
    source = Path(manifest["source"])
    answers = manifest.get("answers")
    commands = tuple(manifest.get("event_commands_sha256", {}))
    log_event_ids = manifest.get("log_event_ids", [])
    render_folders = manifest.get("render_folders")
    as_of = manifest.get("as_of") or datetime.now().isoformat(sep=" ", timespec="seconds")
    if render_folders:
        observable = True
    destination.mkdir(parents=True, exist_ok=False)
    phase_one = destination / "phase_one.py"
    try:
        workflow = _load_phase_one(manifest, source, phase_one)
    except (ValueError, OSError, SyntaxError) as error:
        report = {
            "status": "blocked", "native_vs_phase_one": "pending", "phase_one_vs_phase_two": "pending",
            "standalone_execution": "pending", "phase_two_generation": "blocked",
            "failure": {"type": type(error).__name__, "message": str(error)},
        }
        write_json(destination / "acceptance.json", report)
        return report
    phase_one_sha256 = file_hash(phase_one)
    report = {
        "status": "incomplete", "source": str(source), "source_sha256": manifest["source_sha256"],
        "answers": answers, "phase_one_sha256": phase_one_sha256,
        "native_vs_phase_one": "pending", "phase_one_outcome": "pending",
        "phase_one_vs_phase_two": "pending", "standalone_execution": "pending",
    }
    pkg_dir = destination / "package"
    phase_started = perf_counter()
    pkg_artifact = None
    try:
        pkg_artifact = write_phase_two_candidate(
            workflow, pkg_dir, phase_one_sha256=phase_one_sha256, log_event_ids=log_event_ids,
        )
    except (ValueError, OSError, RuntimeError, KeyError, SyntaxError, ExpressionError) as error:
        report.update(phase_two_generation="failed", failure={"type": type(error).__name__, "message": str(error)})
    else:
        report.update(
            phase_two_generation="generated",
            phase_two_package=str(pkg_dir),
            phase_two_sha256=pkg_artifact.manifest["generated_sha256"],
        )
    timings["phase_two_compile"] = round(perf_counter() - phase_started, 3)
    write_json(destination / "acceptance.json", report)

    runtime = _case_runtime(manifest)
    sink_names = {
        node.node_id: PureWindowsPath(node.config["normalized"]["file"].split("|||", 1)[0]).name
        for node in workflow.nodes if node.node_id in manifest.get("sink_files", {})
    }
    if len(set(sink_names.values())) != len(sink_names):
        raise ValueError("Delivery verification requires distinct output filenames")
    xlsx_sinks = {name for name in sink_names.values() if Path(name).suffix.lower() == ".xlsx"}

    phase_started = perf_counter()
    try:
        first = capture_python(
            source, workflow=workflow, runtime_config=runtime, evidence_source_sha256=manifest["source_sha256"],
            output_directory=destination / "phase-one-output", answers=answers, event_commands=commands,
            log_event_ids=log_event_ids, render_folders=render_folders, as_of=as_of,
        )
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        first = {
            "source_sha256": manifest["source_sha256"], "producer": "python", "answers": answers,
            "status": "blocked", "failure": {"type": type(error).__name__, "message": str(error)},
            "nodes": {}, "sink_artifacts": {},
        }
    first["phase_one_sha256"] = phase_one_sha256
    first["workflow_source_sha256"] = workflow.source_hash
    timings["phase_one_capture"] = round(perf_counter() - phase_started, 3)
    phase_started = perf_counter()
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
    native = collect_native(native_directory, manual=True, capture_report_fields=table_selection is not None,
                            _verified_manifest=manifest)
    _project_dynamic_probes(native, manifest)
    timings["native_collection"] = round(perf_counter() - phase_started, 3)
    phase_started = perf_counter()
    native_result = compare_runs(native, first, align_checkpoints=table_selection is not None,
                                 presentation_policy=checkpoint_policy(workflow) if table_selection is not None else None)
    for item in native_result["comparisons"]:
        if item.get("direction") and (table_selection is not None or item["status"] in {"mismatch", "incomplete"}):
            node_id = item["node_id"]
            direction, anchor = item["direction"], item["anchor"]
            files = native["capture_files"].get(node_id, {}).get(direction, {})
            if anchor in files:
                item["designer_file"] = files[anchor]
    artifacts = native_result["artifact_differences"]
    _describe_native_artifacts(artifacts, manifest, native_directory,
                               destination / "phase-one-output", first, sink_names)
    coarse_groups = {item["group"] for item in artifacts if item["status"] == "coarse_match"}
    exact_groups = {item["group"] for item in artifacts if item["status"] != "coarse_match"}
    coarse_issues = {f"{group}_mismatch" for group in coarse_groups - exact_groups}
    if native_result["status"] == "mismatch" and coarse_issues == set(native_result["issues"]) and coarse_issues:
        comparisons = native_result["comparisons"]
        if all(item["status"] != "mismatch" for item in comparisons):
            native_result["status"] = "incomplete" if native_result["incomplete_evidence"] or any(
                item["status"] == "incomplete" for item in comparisons
            ) else "coarse_match"
    if table_selection is not None:
        try:
            write_table_reports(destination, native, {**first, "report_snapshots": report_snapshots},
                                native_result, table_selection, dynamic_inputs=manifest.get("dynamic_inputs"),
                                probes=manifest["probes"])
        except OSError as error:
            native_result["table_report_issue"] = str(error)
    write_json(destination / "native-vs-phase-one.json", native_result)
    timings["checkpoint_comparison_and_reports"] = round(perf_counter() - phase_started, 3)
    report.update(native_vs_phase_one=native_result["status"], phase_one_outcome=first["status"])
    if first["failure"]:
        report["phase_one_failure"] = first["failure"]
    if native_result["status"] == "mismatch":
        report["status"] = "mismatch"
    if log_event_ids:
        report["logging_events"] = logging_evidence
    if render_folders:
        report["render_workbooks"] = {
            "designer": native["render_workbooks"],
            "phase_one": first.get("workbooks", {}),
        }
    if as_of:
        report["as_of"] = as_of
    if pkg_artifact is None or first["status"] == "blocked" or (first["status"] != "success" and not observable):
        if pkg_artifact is None and report["status"] != "mismatch":
            report["status"] = "blocked"
        timings["total"] = round(perf_counter() - started, 3)
        report["timings_seconds"] = timings
        write_json(destination / "acceptance.json", report)
        return report

    phase_started = perf_counter()
    try:
        delivery_profile = XLSX_PROFILE if render_folders else None
        delivery_dir = destination / "delivery-output"
        expected_files = {sink_names[node_id]: digest for node_id, digest in first["sink_artifacts"].items()}
        expected_files.update({f"events/{name}": digest for name, digest in first.get("event_artifacts", {}).items()})
        case_overrides = _delivery_case_config(pkg_artifact, workflow, manifest, runtime)
        case_config_path = destination / "case_config.json"
        write_json(case_config_path, case_overrides)

        delivery_events = delivery_dir / "events" if commands else delivery_dir
        audit_path = destination / "phase-two-audit.jsonl"
        process = _run_package_subprocess(
            pkg_dir,
            config_path=case_config_path,
            input_dir=source.parent,
            output_dir=delivery_dir,
            events_dir=delivery_events,
            commands=commands,
            log_args=[*log_args, "--audit-log", str(audit_path)],
            as_of=as_of,
            timeout=timeout,
        )
        (destination / "standalone.stdout.txt").write_bytes(process.stdout)
        (destination / "standalone.stderr.txt").write_bytes(process.stderr)
        stderr_lines = process.stderr.decode("utf-8", errors="replace").strip().splitlines()
        failure_kind = stderr_lines[-1].partition(":")[0].rsplit(".", 1)[-1] if stderr_lines else None
        observed_files = _delivery_artifacts(delivery_dir, xlsx_sinks)
        if process.returncode and (stage_failure := _failed_stage(
            audit_path, pkg_artifact.manifest["nodes"], pkg_dir / "pipeline.py", stderr_lines,
        )):
            report["phase_two_stage_failure"] = stage_failure

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
            workbook_match = first["workbooks"] == rendered and (bool(rendered) or first["status"] != "success")
        else:
            workbook_match = True

        for name, change in changed_artifacts(expected_files, observed_files):
            file_differences.append({"filename": name, "status": change})

        if first["status"] == "success":
            outcome_matches = process.returncode == 0
            has_evidence = bool(expected_files or workbook_result) or not observable
        else:
            outcome_matches = process.returncode == 1 and failure_kind == first["failure"]["type"]
            has_evidence = True
        logging_match = _match_logging_events(report.get("logging_events"), phase_two_log, first)

        boundary_cases: dict[str, dict] = {}
        if first["status"] == "success" and outcome_matches and expected_files == observed_files and workbook_match and not delivery_profile:
            boundary_cases = _run_additional_boundary_cases(
                staged_source=source,
                workflow=workflow,
                runtime=runtime,
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

        if (
            p2_status == "mismatch" and first["status"] == "success" and process.returncode == 0
            and not commands
            and all(event.get("kind") == "logging" for event in pkg_artifact.config_spec.events)
            and not any(key.startswith("command_") for key in pkg_artifact.config_spec.operations)
            and all(not entry.get("format", "").startswith("email") for entry in pkg_artifact.config_spec.outputs.values())
        ):
            stages_path = destination / "phase-two-stage-comparison.json"
            try:
                with tempfile.TemporaryDirectory(dir=destination) as temporary:
                    diagnostic_dir = Path(temporary)
                    diagnostic = _run_package_subprocess(
                        pkg_dir, config_path=case_config_path, input_dir=source.parent,
                        output_dir=diagnostic_dir, events_dir=diagnostic_dir, commands=(),
                        log_args=["--workflow-log", str(diagnostic_dir / "events.jsonl")] if log_event_ids else [],
                        as_of=as_of, timeout=timeout,
                        verification_paths=(destination / "phase-one-capture.json", stages_path),
                    )
                    if diagnostic.returncode:
                        report["phase_two_stage_comparison_issue"] = diagnostic.stderr.decode("utf-8", errors="replace").strip()[-2000:]
                    elif stages_path.is_file():
                        stage_report = json.loads(stages_path.read_text(encoding="utf-8"))
                        report["phase_two_stage_comparison"] = stages_path.name
                        if stage_report["first_divergence"]:
                            report["phase_two_first_divergence"] = stage_report["first_divergence"]
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                report["phase_two_stage_comparison_issue"] = str(error)

        comparison_scope = "successful_outputs" if first["status"] == "success" else "failure_behavior"
        if p2_status == "match" and comparison_scope == "successful_outputs":
            pkg_artifact.manifest["python_differential"] = "verified"
            (pkg_dir / "manifest.json").write_text(
                json.dumps(pkg_artifact.manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

        phase_two_result = {
            "profile": "boundary_package",
            "status": p2_status,
            "comparison_scope": comparison_scope,
            "returncode": process.returncode,
            "phase_one_outcome": first["status"],
            "phase_two_failure_type": failure_kind if process.returncode else None,
            **({"phase_two_stage_failure": stage_failure} if report.get("phase_two_stage_failure") else {}),
            **({"nodes": [report["phase_two_first_divergence"]]} if report.get("phase_two_first_divergence") else {}),
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
        report["phase_two_comparison_scope"] = comparison_scope
        report["standalone_execution"] = p2_status
        status = report["native_vs_phase_one"]
        report["status"] = (status if status in {"match", "coarse_match"} and p2_status == "match" and first["status"] == "success"
                            else "mismatch" if "mismatch" in (status, p2_status) else "incomplete")

    except (ValueError, OSError, RuntimeError, KeyError, subprocess.TimeoutExpired) as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        report.update(phase_one_vs_phase_two="incomplete", standalone_execution="incomplete")
    timings["phase_two_compile_run_and_checks"] = round(timings["phase_two_compile"] + perf_counter() - phase_started, 3)
    timings["total"] = round(perf_counter() - started, 3)
    report["timings_seconds"] = timings
    write_json(destination / "acceptance.json", report)
    return report


def _failed_stage(audit_path, nodes, pipeline_path, stderr_lines):
    if not audit_path.is_file():
        return None
    failed = None
    try:
        with audit_path.open(encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                if record.get("kind") == "transform" and record.get("status") == "failed":
                    failed = record
    except (OSError, ValueError):
        return None
    if failed is None:
        return None
    matching = [node for node in nodes if node.get("function") == failed["step"] and not node.get("optimization")]
    node_ids = [node["node_id"] for node in matching]
    code_line = matching[0]["line"] if matching else None
    for trace_line in reversed(stderr_lines):
        location = re.match(r'^\s*File "([^"]+)", line (\d+), in (.+)$', trace_line)
        if location and Path(location[1]) == pipeline_path and location[3] == failed["step"]:
            code_line = int(location[2])
            break
    return {
        "function": failed["step"], "step_index": failed["step_index"], "tool": failed["tool"],
        "type": failed["error_type"], "message": failed["error"], "node_ids": node_ids,
        **({"node_id": node_ids[0]} if len(node_ids) == 1 else {}),
        **({"line": code_line} if code_line else {}),
    }


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
