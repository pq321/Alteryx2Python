"""Four presentation commands backed by recorded migration evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

from .amp_export import EXPORT_DIR, _is_amp, native_probe_path, prepare_amp_export
from .designer_evidence import record_designer_evidence
from .migration import launch_designer, launch_designer_plan, prepare_migration, resume_migration
from .output_comparison import build_output_comparison
from .path_access import PathAccessError, format_path_issue, record_path_issue
from .runner import file_hash, verify_manifest, write_json


def add_parser(subparsers, handler):
    demo = subparsers.add_parser("demo", help="Inspect, run Designer, compare, and present a migration")
    steps = demo.add_subparsers(dest="step", required=True)
    inspect = steps.add_parser("inspect", help="Choose or inspect a workflow and start a presentation case")
    inspect.add_argument("workflow", nargs="?")
    designer = steps.add_parser("designer", help="Stage the inspected workflow and run it in Designer")
    designer.add_argument("--answers", type=Path)
    designer.add_argument("--log-event", action="append", default=[], metavar="ID")
    designer.add_argument("--allow-event-command", action="append", default=[], metavar="PATH")
    designer.add_argument("--designer-pid", type=int)
    designer.add_argument("--designer-launcher", type=Path)
    designer.add_argument("--app-launch", choices=["auto", "wand", "options"], default="auto")
    designer.add_argument("--prepare-only", action="store_true")
    designer.add_argument("--case", type=Path, help="Launch an already prepared case")
    compare = steps.add_parser("compare", help="Collect Designer evidence, compare Phase 1, and verify Phase 2")
    compare.add_argument("node", nargs="?", help="Node ID to highlight")
    compare.add_argument("--anchor", help="Anchor to highlight for the selected node")
    compare.add_argument("--outcome", choices=["success", "failed"])
    compare.add_argument("--failed-node", action="append", default=[])
    compare.add_argument("--skipped-node", action="append", default=[])
    compare.add_argument("--case", type=Path)
    deliver = steps.add_parser("deliver", help="Show the verified Phase 2 script and open an output")
    deliver.add_argument("node", nargs="?", help="Node ID to locate in the generated script")
    deliver.add_argument("--paths-only", action="store_true")
    deliver.add_argument("--case", type=Path)
    demo.set_defaults(func=handler)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _save_latest(state_file, data):
    temporary = state_file.with_name(f".latest-{uuid4().hex}.json")
    write_json(temporary, data)
    temporary.replace(state_file)


def run(args, inspect_workflow, format_inspect):
    root = Path("reports/demo").resolve()
    state_file = root / "latest.json"
    if args.step == "inspect":
        report, status = inspect_workflow(argparse.Namespace(
            workflow=args.workflow, summary=True, compact=False, output_dir=None, answers=None,
        ))
        if report["status"] != "cancelled":
            source = Path(report["workflow"]["source_file"])
            root.mkdir(parents=True, exist_ok=True)
            _save_latest(state_file, {
                "workflow": str(source), "sha256": file_hash(source),
                "inspection": str(Path(report["inspect_report"]).parent),
            })
        return {**report, "display": format_inspect(report) + (
            "\nNext: demo designer" if report["status"] != "cancelled" else ""
        )}, status
    state = _read(state_file) if state_file.is_file() else {}
    if args.step == "designer":
        return _designer(args, state_file, state)
    case_value = args.case or state.get("case")
    if case_value is None:
        raise ValueError("Run demo designer first, or supply --case.")
    case = Path(case_value).resolve()
    if args.step == "compare":
        return _compare(args, case)
    return _deliver(args, case)


def _show_path_warnings(case):
    report = case / "path-issues.json"
    if report.is_file():
        for issue in _read(report):
            if issue["severity"] == "warning":
                print("Path warning: " + format_path_issue(issue), file=sys.stderr, flush=True)
    return report


def _designer(args, state_file, state):
    if args.case is not None:
        case = args.case.resolve()
        result = _read(case / "migration.json")
        state_file.parent.mkdir(parents=True, exist_ok=True)
        _save_latest(state_file, {"case": str(case)})
    else:
        if "workflow" not in state:
            raise ValueError("Run demo inspect <workflow> first.")
        source = Path(state["workflow"])
        if file_hash(source) != state["sha256"]:
            raise ValueError("Workflow changed since inspection. Run demo inspect again.")
        inspection = Path(state["inspection"])
        case = inspection / f"case-{uuid4().hex[:12]}"
        _save_latest(state_file, {**state, "case": str(case)})
        print(f"Preparing case: {case}", file=sys.stderr, flush=True)
        saved = _read(inspection / "inspect.json")
        is_app = source.suffix.lower() == ".yxwz"
        event_ids = args.log_event or _choose_logging_events(source)
        try:
            result = prepare_migration(
                source, case, supplied=_read(args.answers) if args.answers else None,
                interactive=is_app and bool(saved.get("questions")) and not args.answers,
                event_commands=tuple(args.allow_event_command), log_event_ids=event_ids,
            )
        except (OSError, ValueError):
            report = _show_path_warnings(case)
            if report.is_file():
                print(f"Path diagnostics: {report}", file=sys.stderr, flush=True)
            raise
    try:
        manifest = verify_manifest(case / "native")
    except PathAccessError as error:
        record_path_issue(case, error.issue)
        raise
    lines = [f"Case: {case}", f'Inputs: {case / "inputs.json"}', f'Events: {case / "events.json"}',
             f'Engine: {manifest["engine_mode"]}', f'Designer workflow: {result["native_workflow"]}']
    path_report = _show_path_warnings(case)
    if path_report.is_file():
        lines.append(f"Path diagnostics: {path_report}")
    if result.get("answers"):
        lines.append(f'App answers: {result["answers"]}')
    if args.prepare_only:
        lines.append(f'Next: demo designer --case "{case}"')
        return {**result, "display": "\n".join(lines)}, 0
    try:
        receipt = launch_designer(case, args.app_launch, args.designer_pid, args.designer_launcher)
    except PathAccessError as error:
        record_path_issue(case, error.issue)
        raise
    result["designer"] = receipt
    if args.designer_pid is not None:
        result["designer_requested_pid"] = args.designer_pid
    if args.designer_launcher:
        result["designer_launcher"] = str(args.designer_launcher.resolve())
    write_json(case / "migration.json", result)
    lines.extend((f'Designer: {receipt["status"]}', f'Results: {case / "designer-run.json"}'))
    if receipt.get("session") and receipt.get("designer_pid"):
        lines.append(f'Designer session: {receipt["session"]} (PID {receipt["designer_pid"]})')
    if receipt.get("stage"):
        lines.append(f'Designer stage: {receipt["stage"]}')
    if receipt.get("finish_clicked"):
        lines.append("Designer clicked Finish after verifying the supported App answers.")
    if receipt.get("dismissed_alteryx_one"):
        lines.append(f'Alteryx One prompts dismissed: {receipt["dismissed_alteryx_one"]}')
    if receipt.get("screenshot"):
        lines.append(f'Results screenshot: {receipt["screenshot"]}')
    completed = receipt["status"] in {"outputs_ready", "app_failed"} or receipt.get("app_outcome") in {"success", "failed"}
    if manifest["engine_mode"] == "amp" and completed:
        lines.append("AMP probes will be exported during compare.")
    if receipt.get("detail"):
        lines.append(receipt["detail"])
        if receipt.get("status") == "app_failed":
            detail = receipt["detail"].replace("\\", "/").casefold()
            for path, origin in manifest.get("input_origins", {}).items():
                if path.replace("\\", "/").casefold() in detail:
                    issue = PathAccessError("Designer reported an error for the input snapshot", path, receipt["detail"],
                                            consumers=origin.get("consumers", []), source=origin.get("source"))
                    record_path_issue(case, issue.issue)
                    lines.append(str(issue))
            if path_report.is_file() and f"Path diagnostics: {path_report}" not in lines:
                lines.append(f"Path diagnostics: {path_report}")
    if completed:
        lines.append("Next: demo compare")
    return {**result, "display": "\n".join(lines)}, 0 if completed else 1


def _choose_logging_events(source):
    from alteryx2python.workflow_events import workflow_events

    options = [
        event for event in workflow_events(source.read_bytes())
        if event.get("program") and event.get("when") == "after"
    ]
    if not options:
        return []
    print("After Run commands. Enter the IDs of logging-only events to migrate to local JSONL.", file=sys.stderr)
    for event in options:
        print(f'  {event["id"]}: {event["program"]}', file=sys.stderr)
    return [
        item.strip() for item in _prompt("Logging event IDs (comma-separated, Enter to leave unchanged): ").split(",")
        if item.strip()
    ]


def _prompt(label):
    print(label, end="", file=sys.stderr, flush=True)
    value = sys.stdin.readline()
    if not value:
        raise ValueError("Input ended. Supply the recorded answers or outcome explicitly.")
    return value.strip()


def _export_amp_probes(case, manifest, migration, skipped):
    native = case / "native"
    probes = [native / probe["file"] for probe in manifest["probes"] if probe["node_id"] not in skipped]
    amp = [path for path in probes if path.is_file() and _is_amp(path)]
    if not amp:
        return
    export = native / EXPORT_DIR
    receipt_path = export / "manifest.json"
    if receipt_path.is_file() and all(native_probe_path(path).is_file() for path in amp):
        return
    if receipt_path.is_file():
        receipt = _read(receipt_path)
        plan_entry = {
            "workflow": str(export / receipt["instrumented_file"]),
            "status": "ready", "run_dir": str(export),
        }
    else:
        plan_entry = prepare_amp_export(native)
    plan = case / "amp-export-plan.json"
    write_json(plan, [plan_entry])
    print("Exporting AMP probes in Designer...", file=sys.stderr, flush=True)
    report = case / f"amp-export-run-{uuid4().hex[:8]}.json"
    launcher = migration.get("designer_launcher")
    result = launch_designer_plan(plan, report, "auto", migration.get("designer_requested_pid"),
                                  Path(launcher) if launcher else None)
    if result["status"] != "outputs_ready":
        detail = result.get("detail") or "Designer did not produce the expected export."
        raise ValueError(f'AMP export {result["status"]}. {detail} See {report}.')


def _compare(args, case):
    native = case / "native"
    manifest = verify_manifest(native)
    migration = _read(case / "migration.json")
    outcome = args.outcome
    failed = args.failed_node
    skipped = args.skipped_node
    if (failed or skipped) and outcome is None:
        raise ValueError("Node attestations require --outcome.")
    receipt_path = case / "designer-run.json"
    manual = (native / "manual-review.json").is_file()
    existing = manual or (native / "native-run.json").is_file()
    if outcome is None and not existing and migration.get("designer", {}).get("reason") == "designer_report_unavailable":
        raise ValueError(migration["designer"]["detail"])
    if outcome is None and not existing and not receipt_path.is_file():
        raise ValueError("No Designer run evidence. Run demo designer or supply an observed outcome explicitly.")
    export_issue = None
    try:
        _export_amp_probes(case, manifest, migration, set(skipped))
    except (OSError, ValueError) as error:
        if outcome is not None or manual:
            raise
        export_issue = str(error)
    evidence_path = native / "designer-evidence.json"
    evidence = None
    if outcome is None and not existing:
        receipts = _read(receipt_path)
        if not isinstance(receipts, list) or len(receipts) != 1:
            raise ValueError("Expected one Designer run receipt for the prepared case")
        evidence = record_designer_evidence(native, manifest, receipts[0], receipt_path=receipt_path)
    result = resume_migration(case, native_outcome=outcome, failed_nodes=failed, skipped_nodes=skipped)
    delivery = Path(result["report"]).parent
    native_report = delivery / "native-vs-phase-one.json"
    parity = _read(native_report)
    comparisons = parity["comparisons"]
    mismatches = [item for item in comparisons if item["status"] in {"mismatch", "incomplete"}]
    missing = parity.get("missing_native_outputs", []) or parity.get("unreadable_native_outputs", [])
    business_nodes = {node["node_id"] for node in manifest["nodes"]
                      if node["tool_type"] not in {"TextInput", "DbFileInput"}}
    business_outputs = [item for item in comparisons if item.get("direction") == "outputs"
                        and item["node_id"] in business_nodes]
    node_id = args.node or (mismatches or missing or business_outputs or comparisons or [{}])[0].get("node_id")
    shown = [item for item in comparisons if item["node_id"] == node_id
             and (not args.anchor or item.get("anchor") == args.anchor)]
    lines = [f'Overall: {result["status"]} | Designer / Phase 1: {result["native_vs_phase_one"]}',
             f'Phase 1 / Phase 2: {result["phase_one_vs_phase_two"]} | Standalone: {result["standalone_execution"]}']
    if evidence:
        lines.append(f'Designer outcome: {evidence["status"]} | Confirmed skipped nodes: {len(evidence["skipped_nodes"])}')
        lines.append(f'Designer evidence: {evidence_path}')
    if export_issue:
        lines.append(f"AMP export evidence incomplete: {export_issue}")
    for item in shown[:6]:
        lines.append(f'Node {node_id} {item.get("direction", "")}/{item.get("anchor", "")}: {item["status"]}')
    if node_id and not shown:
        lines.append(f"Node {node_id}: no comparison for the requested anchor.")
    if mismatches:
        first = mismatches[0]
        detail = (first.get("value_differences") or first.get("differences") or [{}])[0]
        lines.append(f'First difference: node {first["node_id"]} {first.get("anchor", "")} {json.dumps(detail, ensure_ascii=False)[:180]}')
    elif missing:
        first = missing[0]
        lines.append(f'First missing or unreadable evidence: node {first["node_id"]} {first["anchor"]} ({first["file"]})')
    elif parity["issues"] or parity["incomplete_evidence"]:
        lines.append("First finding: " + (parity["issues"] or parity["incomplete_evidence"])[0])
    elif result["phase_one_vs_phase_two"] == "mismatch":
        phase_two_report = delivery / "phase-one-vs-phase-two.json"
        observed = _read(phase_two_report)
        expected_files = {**observed["phase_one_files"], **observed.get("phase_one_workbooks", {})}
        actual_files = {**observed["phase_two_files"], **observed.get("phase_two_workbooks", {})}
        first_file = next((name for name in sorted(expected_files.keys() | actual_files.keys())
                           if expected_files.get(name) != actual_files.get(name)), None)
        message = f"First output difference: {first_file}" if first_file else "Phase 2 outcome or logging differs."
        lines.append(f"{message} See {phase_two_report}.")
    if result.get("failure"):
        lines.append(f'Execution: {result["failure"]["message"]}')
    write_json(case / "presentation-result.json", {"report": result["report"], "node": node_id})
    lines.extend((f"Node comparison: {native_report}", f'Acceptance report: {result["report"]}', "Next: demo deliver"))
    return {**result, "display": "\n".join(lines)}, 0 if result["status"] == "match" else 1


def _deliver(args, case):
    if not (case / "presentation-result.json").is_file():
        raise ValueError("Run demo compare first.")
    selection = _read(case / "presentation-result.json")
    report_path = Path(selection["report"])
    result = _read(report_path)
    directory = report_path.parent
    script = directory / "phase_two.py"
    manifest_path = directory / "phase_two.manifest.json"
    has_script = script.is_file() and manifest_path.is_file()
    node_id = args.node or selection.get("node")
    nodes = _read(manifest_path)["nodes"] if has_script else []
    entry = next((item for item in nodes if item["node_id"] == node_id and item.get("line")), None)
    line = entry["line"] if entry else None
    output_dir = directory / "delivery-output"
    outputs = sorted((path for path in output_dir.rglob("*") if path.is_file()),
                     key=lambda path: (len(path.relative_to(output_dir).parts), path))
    preview = next((path for path in outputs if path.suffix.lower() in {".xlsx", ".csv", ".tsv", ".txt"}), None)
    output = preview or (outputs[0] if outputs else None)
    native = case / "native"
    pairs = build_output_comparison(native, directory) if (native / "manifest.json").is_file() else []
    lines = [
        f'Overall: {result["status"]} | Standalone: {result["standalone_execution"]}',
        (f'Phase 2: {script}' + (f':{line} (node {node_id})' if line else "")) if has_script else 'Phase 2 code unavailable.',
        f'Acceptance report: {report_path}',
    ]
    if pairs:
        lines.append(f'Side-by-side outputs: {directory / "side-by-side"}')
        for pair in pairs:
            python_label = f'Python Phase {pair["python_phase"]}' if pair["python"] else "Python"
            lines.extend((f'  Alteryx: {pair["alteryx"] or "no corresponding artifact"}',
                          f'  {python_label}: {pair["python"] or "no corresponding artifact"}'))
    else:
        lines.append(f'Output: {output or "none recorded"}')
    if result.get("phase_two_bindings"):
        lines.append(f'Runtime bindings: {result["phase_two_bindings"]}')
    elif result.get("phase_two_reuse_blocker"):
        lines.append(f'Phase 2 mode: {result["phase_two_mode"]} (case replay)')
        lines.append(f'Reusable compilation: {result["phase_two_reuse_blocker"]}')
    if result.get("logging_events"):
        lines.append("Selected After Run events use local Python JSONL logging for this case.")
    if node_id and not entry and has_script:
        lines.append(f"Node {node_id} has no dedicated source location in this build.")
    if not args.paths_only and os.name == "nt":
        try:
            if has_script:
                editor = shutil.which("code.exe")
                launcher = shutil.which("code.cmd")
                if not editor and launcher:
                    candidate = Path(launcher).parent.parent / "Code.exe"
                    editor = str(candidate) if candidate.is_file() else None
                if editor:
                    subprocess.Popen([editor, "--goto", f"{script}:{line or 1}"])
                else:
                    subprocess.Popen(["notepad.exe", str(script)])
            pair = next((entry for entry in pairs if entry["alteryx"] and entry["python"]), pairs[0] if pairs else None)
            candidates = (pair["alteryx"], pair["python"]) if pair else (preview,)
            for candidate in candidates:
                if candidate and candidate.suffix.lower() in {".xlsx", ".csv", ".tsv", ".txt"}:
                    os.startfile(str(candidate))
        except OSError as exc:
            lines.append(f"Could not open a preview: {exc}")
    return {**result, "display": "\n".join(lines)}, 0 if result["status"] == "match" else 1
