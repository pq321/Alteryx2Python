"""Four presentation commands backed by recorded migration evidence."""

from __future__ import annotations

import argparse
from html import escape
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import quote
import warnings
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
    log = report.with_suffix(".log")
    launcher = migration.get("designer_launcher")
    result = launch_designer_plan(plan, report, "auto", migration.get("designer_requested_pid"),
                                  Path(launcher) if launcher else None, log=log)
    if result["status"] != "outputs_ready":
        detail = result.get("detail") or "Designer did not produce the expected export."
        raise ValueError(f'AMP export {result["status"]}. {detail} See {report} and {log}.')
    return log


def _table_text(value):
    return escape(value.replace("\\", "\\\\").replace("\n", " ").replace("\r", " ")).replace("|", r"\|")


def _report_link(label, path, delivery, line=None):
    relative = Path(os.path.relpath(path, delivery)).as_posix()
    destination = quote(relative)
    suffix = f"#L{line}" if line else ""
    label = _table_text(label).replace("[", r"\[").replace("]", r"\]")
    return f"[{label}]({destination}{suffix})"


def _snapshot_lines(path, anchors):
    # write_json uses two-space indentation. Index only keys under nodes/inputs or nodes/outputs.
    def heading(key, indentation):
        return " " * indentation + json.dumps(key, ensure_ascii=False) + ": {"

    wanted = {
        (heading(owner, 4), heading(direction, 6), heading(anchor, 8)): (owner, direction, anchor)
        for owner, direction, anchor in anchors
    }
    if not wanted or not path.is_file():
        return {}
    lines = {}
    with path.open(encoding="utf-8") as capture:
        for line_number, line in enumerate(capture, 1):
            if line.rstrip() == '  "nodes": {':
                break
        else:
            return lines
        owner = direction = ""
        for line_number, line in enumerate(capture, line_number + 1):
            if line.startswith("  }"):
                break
            if line.startswith('    "'):
                owner, direction = line.rstrip(), ""
            elif line.startswith('      "'):
                direction = line.rstrip()
            elif line.startswith('        "') and (key := wanted.pop((owner, direction, line.rstrip()), None)):
                lines[key] = line_number
                if not wanted:
                    break
    return lines


def _comparison_links(native, delivery, anchor_findings, artifacts):
    anchor_keys = {
        (item["node_id"], item["direction"], item["anchor"]) for item in anchor_findings
        if item.get("missing_from") != "Phase 1"
    }
    capture = delivery / "phase-one-capture.json"
    snapshot_lines = _snapshot_lines(capture, anchor_keys)
    designer, phase_one = {}, {}
    for item in anchor_findings:
        owner, direction, anchor = item["node_id"], item["direction"], item["anchor"]
        label = f"{direction[:-1].title()} / {anchor}"
        if filename := item.get("designer_file"):
            path = native / filename
            if path.is_file():
                designer.setdefault(owner, []).append(_report_link(label, path, delivery))
        if line := snapshot_lines.get((owner, direction, anchor)):
            phase_one.setdefault(owner, []).append(_report_link(label, capture, delivery, line))
    for item in artifacts:
        if owner := item.get("node_id"):
            label = item.get("phase_one_filename", item["filename"])
            for links, field, folder in (
                (designer, "designer_file", native),
                (phase_one, "phase_one_file", delivery / "phase-one-output"),
            ):
                if filename := item.get(field):
                    path = folder / filename
                    if path.is_file():
                        links.setdefault(owner, []).append(_report_link(label, path, delivery))
    return designer, phase_one


def _mismatch_total(status, findings, file_findings=()):
    """Count each node once, each unassigned file once, or a workflow-only mismatch."""
    owners = {item["node_id"] for group in (findings, file_findings) for item in group if item.get("node_id")}
    count = len(owners) + sum(not item.get("node_id") for item in file_findings)
    if status == "mismatch":
        return max(count, 1)
    return count if count or status == "match" else "—"


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
    export_issue = export_log = None
    try:
        export_log = _export_amp_probes(case, manifest, migration, set(skipped))
    except (OSError, ValueError) as error:
        if outcome is not None or manual:
            raise
        export_issue = str(error)
    evidence_path = native / "designer-evidence.json"
    if outcome is None and not existing:
        receipts = _read(receipt_path)
        if not isinstance(receipts, list) or len(receipts) != 1:
            raise ValueError("Expected one Designer run receipt for the prepared case")
        record_designer_evidence(native, manifest, receipts[0], receipt_path=receipt_path)
    with warnings.catch_warnings(record=True) as recorded_warnings:
        result = resume_migration(case, native_outcome=outcome, failed_nodes=failed, skipped_nodes=skipped,
                                  table_selection=(args.node, args.anchor))
    delivery = Path(result["report"]).parent
    native_report = delivery / "native-vs-phase-one.json"
    parity = _read(native_report)
    comparisons = parity["comparisons"]
    mismatches = [item for item in comparisons if item["status"] == "mismatch" and not item.get("duplicates_upstream")]
    incomplete = [item for item in comparisons if item["status"] == "incomplete"]
    aligned = [item for item in comparisons if item["status"] == "match" and item.get("order_differences")]
    missing = [*parity.get("missing_native_outputs", []), *parity.get("unreadable_native_outputs", [])]
    tools = {node["node_id"]: node["tool_type"] for node in manifest["nodes"]}
    artifacts = parity.get("artifact_differences", [])
    outcomes = parity.get("outcome_differences", [])
    phase_two_report = delivery / "phase-one-vs-phase-two.json"
    native_status, phase_two_status = result["native_vs_phase_one"], result["phase_one_vs_phase_two"]
    phase_two_findings = []
    phase_two_files = []
    has_phase_two_report = phase_two_report.is_file()
    if has_phase_two_report and phase_two_status == "mismatch":
        phase_two = _read(phase_two_report)
        phase_two_findings = [item for item in phase_two.get("nodes", []) if item["status"] != "match"]
        phase_two_files = phase_two.get("file_differences", [])
    business_nodes = {node_id for node_id, tool in tools.items() if tool not in {"TextInput", "DbFileInput"}}
    business_outputs = [item for item in comparisons if item.get("direction") == "outputs"
                        and item["node_id"] in business_nodes]
    node_id = args.node or next((item["node_id"] for group in
                                 (mismatches, incomplete, missing, outcomes, artifacts, phase_two_findings, aligned,
                                  business_outputs, comparisons)
                                 for item in group if item.get("node_id")), None)
    overview = [
        f'Overall: {result["status"]} | Designer / Phase 1: {result["native_vs_phase_one"]} | '
        f'Phase 1 / Phase 2: {result["phase_one_vs_phase_two"]} | Standalone: {result["standalone_execution"]}',
        f'Designer / Phase 1: {len(mismatches)} anchor mismatches, {len(incomplete)} incomplete anchors, '
        f'{len(artifacts)} output differences.',
    ]
    if aligned:
        overview[-1] += f" {len(aligned)} matched after reordering."
    native_count = _mismatch_total(native_status, [*mismatches, *outcomes], artifacts)
    phase_two_count = _mismatch_total(phase_two_status, phase_two_findings, phase_two_files)
    phase_two_label = "[Phase 1 / Phase 2](phase-one-vs-phase-two.json)" if has_phase_two_report else "Phase 1 / Phase 2"
    report_lines = [
        "# Step 3 comparison", "",
        "| Comparison | Status | Mismatches |",
        "| --- | --- | ---: |",
        f"| [Designer / Phase 1](native-vs-phase-one.json) | {native_status} | {native_count} |",
        f"| {phase_two_label} | {phase_two_status} | {phase_two_count} |",
    ]

    findings = {}
    for label, items in (
        ("output mismatch", [item for item in mismatches if item.get("direction") == "outputs"]),
        ("input mismatch", [item for item in mismatches if item.get("direction") == "inputs"]),
        ("execution mismatch", outcomes),
        ("output file mismatch", artifacts),
        ("incomplete evidence", [*incomplete, *missing]),
        ("Phase 1 / Phase 2 mismatch", phase_two_findings),
    ):
        for item in items:
            if owner := item.get("node_id"):
                findings.setdefault(owner, set()).add(label)
    for reason in parity["incomplete_evidence"]:
        parts = reason.split("_", 2)
        if len(parts) == 3 and parts[0] == "node" and parts[1].isdecimal():
            findings.setdefault(parts[1], set()).add("incomplete evidence")

    anchor_labels = {}
    table_links = {}
    for item in sorted(mismatches, key=lambda item: item["direction"] != "outputs"):
        owner, direction, anchor = item["node_id"], item["direction"], item["anchor"]
        label = f"{direction[:-1].title()} / {anchor}"
        anchor_label = _table_text(label)
        if owner == node_id and anchor == args.anchor:
            anchor_label = f"**{anchor_label}**"
        anchor_labels.setdefault(owner, []).append(anchor_label)
        if filename := item.get("table_report"):
            table_links.setdefault(owner, []).append(_report_link(label, delivery / filename, delivery))
    context_nodes = {item.get("node_id") for item in [*artifacts, *outcomes]} - table_links.keys()
    input_context = {}
    for item in [*comparisons, *parity.get("unassessed_table_reports", [])]:
        owner = item["node_id"]
        if owner in context_nodes and item.get("direction") == "inputs" and not item.get("duplicates_upstream"):
            if filename := item.get("table_report"):
                input_context.setdefault(owner, []).append(filename)
    for owner, filenames in input_context.items():
        table_links[owner] = [
            _report_link("Input context" if len(filenames) == 1 else f"Input context {index}", delivery / filename, delivery)
            for index, filename in enumerate(filenames, 1)
        ]
    designer_links, phase_one_links = _comparison_links(native, delivery, mismatches, artifacts)
    report_lines.extend(["", "## Nodes to review", ""])
    if findings:
        report_lines.extend([
            "| Node | Status | Unmatched anchors (Designer / Phase 1) | Side-by-side comparison (HTML) | Alteryx | Python Phase 1 |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
    for owner in sorted(findings, key=lambda key: (len(key), key)):
        tool = f" ({tools[owner]})" if owner in tools else ""
        label = f"Node {owner}{tool}"
        if args.node == owner:
            label = f"**{label}**"
        status = " · ".join(sorted(findings[owner]))
        designer = ", ".join(designer_links.get(owner, ())) or "—"
        phase_one = ", ".join(phase_one_links.get(owner, ())) or "—"
        anchors = "<br>".join(anchor_labels.get(owner, ())) or "—"
        tables = "<br>".join(table_links.get(owner, ())) or "—"
        report_lines.append(f"| {label} | {_table_text(status)} | {anchors} | {tables} | {designer} | {phase_one} |")
    if not findings:
        report_lines.append("No node-level findings.")
    report_lines.append("")
    if result.get("failure"):
        report_lines.append("- Execution failed. See the acceptance report.")
    acceptance_details = {}
    if export_issue:
        acceptance_details["amp_export_issue"] = export_issue
    if recorded_warnings:
        acceptance_details["runtime_warnings"] = [
            {"category": warning.category.__name__, "message": str(warning.message)}
            for warning in recorded_warnings
        ]
        report_lines.append(f"- Runtime warnings: {len(recorded_warnings)}. See the acceptance report.")
    if acceptance_details:
        acceptance_path = Path(result["report"])
        write_json(acceptance_path, {**_read(acceptance_path), **acceptance_details})

    report_lines.extend(["", "## Evidence files", "", "- [Acceptance](acceptance.json)"])
    if evidence_path.is_file():
        report_lines.append("- " + _report_link("Designer run and skipped nodes", evidence_path, delivery))
    if (delivery / "standalone.json").is_file():
        report_lines.append("- [Independent Phase 2 run](standalone.json)")
    if export_issue:
        report_lines.append("- AMP export evidence incomplete. See the acceptance report.")
    if export_log:
        report_lines.append("- " + _report_link("AMP export log", export_log, delivery))
    if parity.get("table_report_issue"):
        report_lines.append("- Some table views could not be saved. See the Designer / Phase 1 evidence.")
    comparison_report = delivery / "comparison-summary.md"
    comparison_report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    write_json(case / "presentation-result.json", {
        "report": result["report"], "node": node_id, "comparison_report": str(comparison_report),
    })
    lines = [*overview, f"Comparison report: {comparison_report}"]
    return {**result, "comparison_report": str(comparison_report), "display": "\n".join(lines)}, 0 if result["status"] == "match" else 1


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
