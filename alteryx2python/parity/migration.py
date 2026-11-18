"""Prepare and resume a local Designer migration using one recorded case."""

from dataclasses import asdict
from datetime import date, datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET

from alteryx2python.generator.macro_sources import resolve_macro_path
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.app_config import _typed, bind_answers, configure_workflow, question_manifest
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import _target_ancestor_node_ids, _topological_order, run_workflow_graph
from alteryx2python.runtime.scheduling import container_guards, detour_exclusions
from alteryx2python.runtime.variables import resolve_variable_tokens, workflow_variables
from alteryx2python.tools.delivery import XLSX_PROFILE
from alteryx2python.tools.dynamicinput import read_list_options
from alteryx2python.workflow_audit import audit_workflow
from alteryx2python.workflow_events import bind_logging_events, workflow_events

from .delivery import verify_delivery
from .local_adapters import field_reference, formula_text, insert_input_formula
from .manual import attest_native
from .runner import _dynamic_local_tools, file_hash, prepare, verify_manifest, write_json


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
    return entries


def _stage_dynamic_inputs(staged, source_dir, document, answers, entries, allow_missing, as_of):
    """Freeze the file list for this case before opening Designer."""
    workflow = XmlWorkflowParser().parse(staged)
    nodes = {node.node_id: node for node in workflow.nodes}
    _, detour_skips = detour_exclusions(workflow.nodes, workflow.edges) if answers is None else (set(), set())
    selected = {
        node.node_id for node in workflow.nodes if node.tool_type == "DynamicInput"
        and node.node_id not in detour_skips
        and not (answers is None and None in container_guards(node, nodes, ()))
    }
    if not selected:
        return {}
    configured, _ = configure_workflow(document, answers) if answers is not None else (document, {})
    configured_nodes = {node.get("ToolID"): node for node in configured.iter("Node")}
    elements = {node.get("ToolID"): node for node in document.iter("Node")}
    variables = workflow_variables(workflow)
    variables.update({f"Question.{name}": value for name, value in (answers or {}).items()})
    local_tools = _dynamic_local_tools() - {"Directory", "DbFileOutput"}
    next_id = max(map(int, elements)) + 1
    adapters = {}
    for node_id in _topological_order(workflow.nodes, workflow.edges):
        if node_id not in selected:
            continue
        node = nodes[node_id]
        config = elements[node_id].find("Properties/Configuration")
        actual = configured_nodes[node_id].find("Properties/Configuration")
        if ET.tostring(config) != ET.tostring(actual):
            raise ValueError(f"App Action changes Dynamic Input {node_id}'s configuration; its file list cannot be frozen")
        field, reference, behaviour, _ = read_list_options(node.config["normalized"])
        incoming = [edge for edge in workflow.edges if edge.target_node_id == node_id and edge.target_anchor == "Input"]
        if len(incoming) != 1:
            raise ValueError(f"Dynamic Input {node_id} requires one upstream file list")
        edge = incoming[0]
        targets = {edge.source_node_id}
        current = XmlWorkflowParser().parse(staged)
        predecessors = _target_ancestor_node_ids(current, targets)
        unsupported = {
            item.tool_type for item in current.nodes
            if item.node_id in predecessors and item.tool_type not in local_tools and item.node_id not in adapters
        }
        if unsupported:
            raise ValueError(f"Dynamic Input {node_id} file-list preflight has no adapter for: {', '.join(sorted(unsupported))}")
        context = WorkflowContext(runtime_config={
            "answers": answers, "_workflow_audit": True, "execute_commands": False, "as_of": as_of,
        })
        run = run_workflow_graph(current, context, target_node_ids=targets)
        result = run.node_results.get(edge.source_node_id)
        frame = result.outputs.get(edge.source_anchor) if result is not None else None
        if frame is None or field not in frame:
            raise ValueError(f"Dynamic Input {node_id} preflight could not read path field {field!r}")
        frozen = {}
        for value in sorted({value for value in frame[field] if isinstance(value, str) and value.strip()}):
            path = _resolve_path(value, variables, f"Dynamic Input {node_id}")
            snapshot = _stage_input(staged.parent, source_dir, path, entries, allow_missing or behaviour == "warning")
            frozen[value] = (staged.parent / snapshot).as_posix()
        reference = _resolve_path(reference, variables, f"Dynamic Input {node_id} template")
        raw, _, sheet = reference.partition("|||")
        if (source_dir / raw).is_file():
            template = _stage_input(staged.parent, source_dir, reference, entries, False)
        else:
            available = next((path for path in frozen.values() if Path(path.partition("|||")[0]).is_file()), None)
            if available is None:
                raise FileNotFoundError(f"Dynamic Input {node_id} has no available template or source file")
            filename, _, available_sheet = available.partition("|||")
            selector = available_sheet or sheet
            template = filename + ("|||" + selector if selector else "")
        config.find("InputConfiguration/Configuration/File").text = (staged.parent / template).as_posix()
        copy_field = f"__a2p_path_{node_id}"
        if copy_field in frame:
            raise ValueError(f"Dynamic Input {node_id} has a conflicting isolation field {copy_field!r}")
        missing = (staged.parent / "inputs" / f"unbound-{node_id}{Path(raw).suffix}").as_posix()
        branches = [f"{field_reference(field)} == {formula_text(value)} THEN {formula_text(path)}"
                    for value, path in frozen.items()]
        expression = "IF " + " ELSEIF ".join(branches) + f" ELSE {formula_text(missing)} ENDIF" if branches else formula_text(missing)
        insert_input_formula(document, node_id, next_id, copy_field, expression)
        config.find("ReadList_Field").text = copy_field
        adapters[node_id] = {"path_field": field, "isolation_tool": str(next_id), "file_count": len(frozen)}
        next_id += 1
        ET.ElementTree(document).write(staged, encoding="utf-8", xml_declaration=True)
    return adapters


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
    write_json(directory / "source-audit.json", audit_workflow(
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
    entries = _stage_workflow(workflow, directory, document, answers, questions, allow_missing)
    write_json(directory / "inputs.json", list(entries.values()))
    if answers is not None:
        write_json(directory / "answers.json", answers)
        configured, _ = configure_workflow(document, answers)
        input_ids = {node.node_id for node in workflow.nodes if node.tool_type == "DbFileInput"}
        frozen = {Path(item["snapshot"]) for item in entries.values()}
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
    as_of = datetime.now().isoformat(sep=" ", timespec="seconds")
    dynamic_inputs = _stage_dynamic_inputs(staged, source.parent, document, answers, entries, allow_missing, as_of)
    write_json(directory / "inputs.json", list(entries.values()))
    staged_workflow = XmlWorkflowParser().parse(staged)
    has_render = any(node.tool_type == "PortfolioComposerRender" for node in staged_workflow.nodes)
    write_json(directory / "audit.json", audit_workflow(
        staged_workflow, answers=answers, parameter_mode="specialized", log_event_ids=log_event_ids,
        delivery_profile=XLSX_PROFILE if has_render else None,
    ))
    native = directory / "native"
    manifest = prepare(staged, native, answers=answers, event_commands=event_commands,
                       capture_reference=False, allow_missing_inputs=allow_missing,
                       instrumented_filename=instrumented_filename, log_event_ids=log_event_ids,
                       dynamic_inputs=dynamic_inputs, isolate_xlsx_render=True,
                       as_of=as_of if dynamic_inputs or has_render else None)
    if answers is not None:
        instrumented = native / manifest["instrumented_file"]
        configured, _ = configure_workflow(instrumented, answers)
        render_configs = {
            node.get("ToolID"): ET.tostring(node.find("Properties/Configuration"))
            for node in ET.parse(instrumented).iter("Node")
            if node.get("ToolID") in manifest.get("render_folders", {})
        }
        for node in configured.iter("Node"):
            expected_render = render_configs.get(node.get("ToolID"))
            if expected_render is not None and ET.tostring(node.find("Properties/Configuration")) != expected_render:
                raise ValueError(f"App Action changes the isolated Render configuration for tool {node.get('ToolID')}")
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
    manifest["inputs_sha256"].update({item["snapshot"]: item["sha256"] for item in entries.values()})
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
    if (directory / "answers.json").is_file():
        print(f"Using recorded App answers from {directory / 'answers.json'}.", file=sys.stderr, flush=True)
    return launch_designer_plan(directory / "designer-plan.json", directory / "designer-run.json", mode, pid, launcher)


def launch_designer_plan(plan, report, mode, pid=None, launcher=None):
    runner = Path(__file__).resolve().parents[2] / "scripts" / "designer_click_run.ps1"
    shell = shutil.which("pwsh")
    if shell is None or not runner.is_file():
        raise ValueError("Designer automation requires PowerShell 7 and the repository scripts directory")
    command = [
        shell, "-NoProfile", "-File", str(runner), "-Plan", str(plan),
        "-Report", str(report), "-AppLaunch", mode, "-ManualAppInputs", "-TimeoutSeconds", "180",
    ]
    if pid:
        command.extend(["-DesignerProcessId", str(pid)])
    if launcher:
        command.extend(["-DesignerLauncher", str(launcher.resolve(strict=True))])
    result = subprocess.run(command, stdout=sys.stderr, check=False)
    if not report.is_file():
        return {"status": "blocked", "returncode": result.returncode}
    return json.loads(report.read_text(encoding="utf-8-sig"))[0]
