"""Prepare and resume a local Designer migration using one recorded case."""

from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET

from alteryx2python.generator.macro_sources import resolve_macro_path
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.app_config import _typed, bind_answers, configure_workflow, question_manifest
from alteryx2python.runtime.scheduling import container_guards
from alteryx2python.runtime.variables import resolve_variable_tokens, workflow_variables
from alteryx2python.workflow_audit import audit_workflow
from alteryx2python.workflow_events import bind_logging_events, workflow_events

from .delivery import verify_delivery
from .manual import attest_native
from .runner import file_hash, prepare, verify_manifest, write_json


def prompt_answers(questions, read=None, display=None):
    read = read or input
    display = display or (lambda message: print(message, file=sys.stderr))
    display("Analytic App answers. Enter accepts the shown default.")
    answers = {}
    for question in questions:
        hint = "YYYY-MM-DD" if question.kind == "Date" else question.kind
        label = question.description or question.name
        if question.choices:
            display("  Choices: " + ", ".join(question.choices))
        while True:
            try:
                raw = read(f"{label} ({hint}) [{question.default}]: ")
                value = raw if raw else question.default
                if question.kind == "Date":
                    if not value or date.fromisoformat(str(value)).isoformat() != value:
                        raise ValueError("Use YYYY-MM-DD")
                answers[question.name] = _typed(question, value)
                break
            except ValueError as error:
                display(str(error))
    return answers


def _stage_input(root, source_dir, value, entries, allow_missing):
    raw, separator, selection = value.partition("|||")
    source = (source_dir / raw).resolve()
    if source.suffix.lower() not in {".csv", ".tsv", ".txt", ".xlsx", ".yxdb"} or "://" in raw:
        raise ValueError(f"Expected a local input file: {raw}")
    entry = entries.get(str(source))
    if entry is None:
        target = root / "inputs" / str(len(entries) + 1) / source.name
        digest = None
        if source.is_file():
            digest = file_hash(source)
            target.parent.mkdir(parents=True)
            shutil.copyfile(source, target)
            if file_hash(target) != digest:
                raise ValueError(f"Input changed while being copied: {source}")
        elif not allow_missing or source.exists():
            raise FileNotFoundError(f"Required input is unavailable: {source}")
        entry = entries[str(source)] = {"source": str(source), "snapshot": str(target), "sha256": digest}
    return Path(entry["snapshot"]).relative_to(root).as_posix() + separator + selection


def _resolve_path(value, variables, location):
    try:
        return resolve_variable_tokens(value, variables)
    except ValueError as error:
        raise ValueError(f"{location}: {error}") from error


def _stage_workflow(workflow, root, document, answers, questions, allow_missing):
    entries = {}
    source_dir = Path(workflow.source_file).parent
    variables = workflow_variables(workflow)
    variables.update({f"Question.{name}": value for name, value in (answers or {}).items()})
    xml_nodes = {node.get("ToolID"): node for node in document.iter("Node")}
    by_id = {node.node_id: node for node in workflow.nodes}
    for node in workflow.nodes:
        if answers is None and None in container_guards(node, by_id, ()):
            continue
        element = xml_nodes[node.node_id]
        config = element.find("Properties/Configuration")
        if node.tool_type == "DbFileInput" and config is not None:
            file = config.find("File")
            if file is not None and file.text:
                path = _resolve_path(file.text, variables, f"Input Data {node.node_id}")
                file.text = _stage_input(root, source_dir, path, entries, allow_missing)
        if node.tool_type.startswith("Macro_"):
            settings = element.find("EngineSettings")
            if settings is None:
                settings = element.find("Properties/EngineSettings")
            if settings is not None and settings.get("Macro"):
                path = resolve_macro_path(settings.get("Macro"), source_dir)
                if path is not None:
                    settings.set("Macro", str(path))
    if answers is not None:
        for question in questions:
            value = answers[question.name]
            if not value or question.kind not in {"FileBrowse", "QuestionFileBrowse", "FolderBrowse"}:
                continue
            value = _resolve_path(str(value), variables, f"{question.kind} {question.name}")
            if question.kind in {"FileBrowse", "QuestionFileBrowse"}:
                staged = _stage_input(root, source_dir, value, entries, allow_missing)
                filename, separator, selection = staged.partition("|||")
                answers[question.name] = str(root / filename) + separator + selection
            if question.kind == "FolderBrowse":
                folder = (source_dir / value).resolve()
                if not folder.is_dir():
                    raise ValueError(f"Folder Browse requires an existing directory: {folder}")
                answers[question.name] = str(folder)
    return list(entries.values())


def prepare_migration(source, directory, *, supplied=None, interactive=False, allow_missing=False, event_commands=(),
                      instrumented_filename=None, log_event_ids=()):
    log_event_ids = tuple(log_event_ids)
    source, directory = source.resolve(), directory.resolve()
    workflow = XmlWorkflowParser().parse(source)
    document = ET.fromstring(workflow.source_xml)
    questions = question_manifest(document)
    is_app = source.suffix.lower() == ".yxwz"
    if source.suffix.lower() not in {".yxmd", ".yxwz"}:
        raise ValueError("Provide a workflow or analytic app. Test macros through a calling workflow.")
    if (supplied is not None or interactive) and not is_app:
        raise ValueError("Question answers require an analytic app (.yxwz)")
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "nodes.json", [
        {"id": node.node_id, "tool": node.tool_type, "configuration": node.config.get("normalized", {})}
        for node in workflow.nodes
    ])
    write_json(directory / "questions.json", [asdict(question) for question in questions])
    try:
        events = workflow_events(workflow.source_xml)
    except (ValueError, NotImplementedError) as error:
        write_json(directory / "events.json", {"events": [], "error": str(error)})
    else:
        selected = bind_logging_events(events, log_event_ids)
        logging_ids = {event["id"] for event in selected if event.get("kind") == "logging"}
        for event in events:
            if event["id"] in logging_ids:
                event["migration"] = {"designer": "excluded", "python": "logging"}
        write_json(directory / "events.json", {"events": events})
    write_json(directory / "audit.json", audit_workflow(
        workflow, answers=supplied, parameter_mode="specialized", log_event_ids=log_event_ids,
    ))
    if interactive:
        supplied = prompt_answers(questions)
    answers = bind_answers(document, supplied)[1] if is_app else None
    if answers is not None:
        for question in questions:
            if question.kind == "Date":
                if not answers[question.name]:
                    raise ValueError(f"Date question {question.name!r} has no saved default. Supply YYYY-MM-DD with --interactive or --answers.")
                answers[question.name] = date.fromisoformat(str(answers[question.name])).isoformat()
    inputs = _stage_workflow(workflow, directory, document, answers, questions, allow_missing)
    write_json(directory / "inputs.json", inputs)
    if answers is not None:
        write_json(directory / "answers.json", answers)
        configured, _ = configure_workflow(document, answers)
        input_ids = {node.node_id for node in workflow.nodes if node.tool_type == "DbFileInput"}
        frozen = {Path(item["snapshot"]) for item in inputs}
        for node in configured.iter("Node"):
            if node.get("ToolID") in input_ids:
                target = node.findtext("Properties/Configuration/File", "").partition("|||")[0]
                if (directory / target).resolve() not in frozen:
                    raise ValueError(f"App Action resolves Input Data {node.get('ToolID')} outside the staged inputs")
        document, _ = configure_workflow(document, answers, apply=False)
    if event_commands:
        _resolve_event_commands(document, source.parent, log_event_ids)
    staged = directory / source.name
    ET.ElementTree(document).write(staged, encoding="utf-8", xml_declaration=True)
    staged_workflow = XmlWorkflowParser().parse(staged)
    write_json(directory / "audit.json", audit_workflow(
        staged_workflow, answers=answers, parameter_mode="specialized", log_event_ids=log_event_ids,
    ))
    native = directory / "native"
    manifest = prepare(staged, native, answers=answers, event_commands=event_commands,
                       capture_reference=False, allow_missing_inputs=allow_missing,
                       instrumented_filename=instrumented_filename, log_event_ids=log_event_ids)
    if answers is not None:
        configured, _ = configure_workflow(native / manifest["instrumented_file"], answers)
        for node in configured.iter("Node"):
            filename = manifest["sink_files"].get(node.get("ToolID"))
            if filename is None:
                continue
            config = node.find("Properties/Configuration")
            actual = config.findtext("File", "").partition("|||")[0]
            multi_file = config.find("MultiFile")
            if Path(actual).resolve() != native / filename or (
                multi_file is not None and multi_file.get("value", "").lower() in {"true", "1"}
            ):
                raise ValueError(f"App Action overrides the isolated output for tool {node.get('ToolID')}")
    # Include all snapshots, including paths selected by app answers.
    manifest["inputs_sha256"].update({item["snapshot"]: item["sha256"] for item in inputs})
    write_json(native / "manifest.json", manifest)
    plan = directory / "designer-plan.json"
    write_json(plan, [{"status": "ready", "workflow": str(staged), "run_dir": str(native)}])
    result = {
        "status": "awaiting_designer", "source": str(source), "source_sha256": file_hash(source),
        "runtime_input_dependencies": [
            node.node_id for node in workflow.nodes
            if node.tool_type in {"DynamicInput", "Directory"} or node.tool_type.startswith("Macro_")
        ],
        "designer_plan": str(plan), "native_workflow": str(native / manifest["instrumented_file"]),
        "answers": str(directory / "answers.json") if is_app else None,
        **({"log_event_ids": manifest["log_event_ids"]} if manifest.get("log_event_ids") else {}),
    }
    write_json(directory / "migration.json", result)
    return result


def _resolve_event_commands(document, source_dir, log_event_ids):
    elements = document.findall("./Properties/Events/Event")
    events = bind_logging_events(workflow_events(ET.tostring(document, encoding="unicode")), log_event_ids)
    for event in events:
        if "program" not in event:
            continue
        element = elements[int(event["id"])]
        for key in ("cmd_Program", "Command", "ProgramName"):
            element.attrib.pop(key, None)
            for child in element.findall(key):
                element.remove(child)
        ET.SubElement(element, "cmd_Program").text = str((source_dir / event["program"]).resolve())


def resume_migration(directory, *, native_outcome=None, failed_nodes=(), skipped_nodes=()):
    directory = directory.resolve()
    native = directory / "native"
    verify_manifest(native)
    if native_outcome:
        attest_native(native, native_outcome, failed_nodes=failed_nodes, skipped_nodes=skipped_nodes)
    attempt = 1
    destination = directory / "delivery"
    while destination.exists():
        attempt += 1
        destination = directory / f"delivery-{attempt}"
    result = verify_delivery(native, destination, observable=True)
    result["report"] = str(destination / "acceptance.json")
    return result


def launch_designer(directory, mode, pid, launcher=None):
    verify_manifest(directory / "native")
    runner = Path(__file__).resolve().parents[2] / "scripts" / "designer_click_run.ps1"
    shell = shutil.which("pwsh")
    if shell is None or not runner.is_file():
        raise ValueError("Designer automation requires PowerShell 7 and the repository scripts directory")
    report = directory / "designer-run.json"
    command = [
        shell, "-NoProfile", "-File", str(runner), "-Plan", str(directory / "designer-plan.json"),
        "-Report", str(report), "-AppLaunch", mode, "-ManualAppInputs", "-TimeoutSeconds", "180",
    ]
    if pid:
        command.extend(["-DesignerProcessId", str(pid)])
    if launcher:
        command.extend(["-DesignerLauncher", str(launcher.resolve(strict=True))])
    if (directory / "answers.json").is_file():
        print(f"Verify Designer's answers against {directory / 'answers.json'} before clicking Finish.", file=sys.stderr, flush=True)
    result = subprocess.run(command, stdout=sys.stderr, check=False)
    if not report.is_file():
        return {"status": "blocked", "returncode": result.returncode}
    return json.loads(report.read_text(encoding="utf-8-sig"))[0]
