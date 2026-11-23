"""Prepare and resume a local Designer migration using one recorded case."""

from dataclasses import asdict
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import shutil
from stat import S_ISDIR
import subprocess
import sys
from xml.etree import ElementTree as ET

from alteryx2python.expressions.errors import ExpressionError
from alteryx2python.generator.macro_sources import resolve_macro_path
from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.generator.readable import read_phase_one
from alteryx2python.input_bindings import STAGEABLE_INPUT_SUFFIXES
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.app_config import _typed, bind_answers, configure_workflow, question_manifest
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import _target_ancestor_node_ids, _topological_order, run_workflow_graph
from alteryx2python.runtime.scheduling import container_guards, detour_exclusions
from alteryx2python.runtime.variables import resolve_variable_tokens, workflow_variables
from alteryx2python.tools.delivery import XLSX_PROFILE
from alteryx2python.tools.dynamicinput import dynamic_source_reference, read_list_options
from alteryx2python.workflow_audit import audit_workflow
from alteryx2python.workflow_events import bind_logging_events, workflow_events

from .delivery import verify_delivery, write_phase_two_candidate
from .local_adapters import field_reference, formula_text, insert_input_formula
from .manual import attest_native
from .path_access import PathAccessError, record_path_issue
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


def _stage_input(root, source_dir, value, entries, allow_missing, *, consumer, folder="inputs"):
    raw, separator, selection = value.partition("|||")
    source = source_dir / raw
    operation = "Resolve input path"
    path = source
    try:
        source = source.resolve()
        if source.suffix.lower() not in STAGEABLE_INPUT_SUFFIXES or "://" in raw:
            raise ValueError(f"Expected a local input file for {consumer['tool']} (Tool ID {consumer['node_id']}): {raw}")
        entry = entries.get(str(source))
        if entry is None:
            operation, path = "Read source input", source
            target = root / folder / str(len(entries) + 1) / source.name
            try:
                digest = file_hash(source)
            except FileNotFoundError:
                if not allow_missing:
                    raise
                digest = None
            if digest is not None:
                operation, path = "Create input snapshot directory", target.parent
                target.parent.mkdir(parents=True)
                operation, path = "Copy input snapshot", target
                shutil.copyfile(source, target)
                operation = "Verify input snapshot"
                if file_hash(target) != digest:
                    raise OSError("Input changed while being copied")
            entry = entries[str(source)] = {
                "source": str(source), "snapshot": str(target), "sha256": digest, "consumers": [],
            }
    except OSError as error:
        issue = PathAccessError(operation, getattr(error, "filename", None) or path, error,
                                consumers=[consumer], source=source)
        record_path_issue(root, issue.issue)
        raise issue from error
    if consumer not in entry["consumers"]:
        entry["consumers"].append(consumer)
        if entry["sha256"] is None:
            warning = PathAccessError("Read source input", source, "File is missing; this input allows missing files",
                                      consumers=[consumer])
            record_path_issue(root, {**warning.issue, "severity": "warning"})
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
                file.text = _stage_input(root, source_dir, path, entries, allow_missing,
                                        consumer={"tool": "Input Data", "node_id": node.node_id})
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
            consumer = {"tool": "Folder Browse" if question.kind == "FolderBrowse" else "File Browse",
                        "node_id": question.node_id, "question": question.name}
            if question.kind in {"FileBrowse", "QuestionFileBrowse"}:
                staged = _stage_input(root, source_dir, value, entries, allow_missing, consumer=consumer)
                filename, separator, selection = staged.partition("|||")
                answers[question.name] = str(root / filename) + separator + selection
            if question.kind == "FolderBrowse":
                folder = source_dir / value
                try:
                    folder = folder.resolve()
                    if not S_ISDIR(folder.stat().st_mode):
                        raise NotADirectoryError("Expected a directory")
                except OSError as error:
                    issue = PathAccessError("Read input folder", folder, error, consumers=[consumer])
                    record_path_issue(root, issue.issue)
                    raise issue from error
                answers[question.name] = str(folder)
    return entries


def _stage_dynamic_inputs(staged, source_dir, document, answers, entries, templates, allow_missing, as_of):
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
        action = node.config["normalized"]["read_list_type"]
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
        consumer = {"tool": "Dynamic Input", "node_id": node_id, "field": field}
        configured_template = reference
        reference = _resolve_path(reference, variables, f"Dynamic Input {node_id} template")
        for value in sorted({value for value in frame[field] if isinstance(value, str) and value.strip()}):
            name = _resolve_path(value, variables, f"Dynamic Input {node_id}")
            try:
                path = dynamic_source_reference(name, reference, action)
            except ValueError as error:
                raise ValueError(f"Dynamic Input {node_id} could not apply {action} to {name!r}") from error
            snapshot = _stage_input(staged.parent, source_dir, path, entries, allow_missing or behaviour == "warning",
                                    consumer=consumer)
            frozen[value] = (staged.parent / snapshot).as_posix()
        raw, _, sheet = reference.partition("|||")
        template_consumer = {**consumer, "field": "Input Data Source Template"}
        source = source_dir / raw
        try:
            source = source.resolve()
            has_template = source.is_file()
        except OSError as error:
            issue = PathAccessError("Read Dynamic Input template", source, error, consumers=[template_consumer])
            record_path_issue(staged.parent, issue.issue)
            raise issue from error
        if has_template:
            if str(source) in entries:
                template = _stage_input(staged.parent, source_dir, reference, entries, False, consumer=template_consumer)
            else:
                template = _stage_input(staged.parent, source_dir, reference, templates, False,
                                        consumer=template_consumer, folder="templates")
            template_origin = str(source)
        else:
            available = next((path for path in frozen.values() if Path(path.partition("|||")[0]).is_file()), None)
            if available is None:
                issue = PathAccessError("Read Dynamic Input template", source, "No accessible template or runtime source file",
                                        consumers=[template_consumer])
                record_path_issue(staged.parent, issue.issue)
                raise issue
            filename, _, available_sheet = available.partition("|||")
            selector = available_sheet or sheet
            template = filename + ("|||" + selector if selector else "")
            template_origin = next(item["source"] for item in entries.values() if Path(item["snapshot"]) == Path(filename))
        template_path = (staged.parent / template).as_posix()
        config.find("InputConfiguration/Configuration/File").text = template_path
        copy_field = f"__a2p_path_{node_id}"
        if copy_field in frame:
            raise ValueError(f"Dynamic Input {node_id} has a conflicting isolation field {copy_field!r}")
        missing = (staged.parent / "inputs" / f"unbound-{node_id}{Path(raw).suffix}").as_posix()
        branches = [f"{field_reference(field)} == {formula_text(value)} THEN {formula_text(path)}"
                    for value, path in frozen.items()]
        expression = "IF " + " ELSEIF ".join(branches) + f" ELSE {formula_text(missing)} ENDIF" if branches else formula_text(missing)
        insert_input_formula(document, node_id, next_id, copy_field, expression)
        config.find("ReadList_Field").text = copy_field
        config.find("ReadList_Type").text = "Path"
        adapters[node_id] = {
            "path_field": field, "isolation_tool": str(next_id), "file_count": len(frozen),
            "template": {"configured": configured_template, "source": template_origin, "snapshot": template_path},
        }
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
    phase_one = directory / "phase_one.py"
    phase_one.write_text(PythonGenerator().generate(workflow), encoding="utf-8", newline="")
    phase_one_sha256 = file_hash(phase_one)
    candidate = directory / "phase-two-candidate"
    result = {"source": str(source), "source_sha256": workflow.source_hash}
    try:
        write_phase_two_candidate(
            read_phase_one(phase_one), candidate,
            phase_one_sha256=phase_one_sha256, log_event_ids=log_event_ids,
        )
    except (ValueError, OSError, RuntimeError, KeyError, SyntaxError, ExpressionError) as error:
        result.update(phase_two_generation="failed", phase_two_failure={
            "type": type(error).__name__, "message": str(error),
        })
    else:
        result.update(phase_two_generation="generated", phase_two_package=str(candidate))

    try:
        result.update(_prepare_validation(
            source, directory, workflow, document, questions, phase_one_sha256,
            supplied=supplied, interactive=interactive, allow_missing=allow_missing,
            event_commands=event_commands, instrumented_filename=instrumented_filename,
            log_event_ids=log_event_ids,
        ))
    except (ValueError, OSError, RuntimeError, KeyError, EOFError) as error:
        result.update(status="incomplete", failure={"type": type(error).__name__, "message": str(error)})
        write_json(directory / "migration.json", result)
        if result.get("phase_two_package"):
            error.add_note(f"Phase 2 candidate (unverified): {candidate}")
        raise

    write_json(directory / "migration.json", result)
    return result


def _prepare_validation(source, directory, workflow, document, questions, phase_one_sha256, *,
                        supplied, interactive, allow_missing, event_commands, instrumented_filename, log_event_ids):
    is_app = source.suffix.lower() == ".yxwz"
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
        staged_input_preflight=True,
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
                    raise ValueError(f"App Action resolves Input Data {node.get('ToolID')} outside the staged inputs: {directory / target}")
        document, _ = configure_workflow(document, answers, apply=False)
    if event_commands:
        _resolve_event_commands(document, source.parent, log_event_ids)
    staged = directory / source.name
    ET.ElementTree(document).write(staged, encoding="utf-8", xml_declaration=True)
    as_of = datetime.now().isoformat(sep=" ", timespec="seconds")
    templates = {}
    dynamic_inputs = _stage_dynamic_inputs(staged, source.parent, document, answers, entries, templates, allow_missing, as_of)
    write_json(directory / "inputs.json", list(entries.values()))
    staged_workflow = XmlWorkflowParser().parse(staged)
    has_render = any(node.tool_type == "PortfolioComposerRender" for node in staged_workflow.nodes)
    write_json(directory / "audit.json", audit_workflow(
        staged_workflow, answers=answers, parameter_mode="specialized", log_event_ids=log_event_ids,
        delivery_profile=XLSX_PROFILE if has_render else None,
    ))
    native = directory / "native"
    if instrumented_filename is None:
        case_id = sha256(str(directory).encode("utf-8")).hexdigest()[:12]
        instrumented_filename = f"instrumented-{case_id}{source.suffix.lower()}"
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
    # Verify all snapshots, including design-time templates and paths selected by app answers.
    for snapshots in (entries, templates):
        manifest["inputs_sha256"].update({item["snapshot"]: item["sha256"] for item in snapshots.values()})
    manifest["input_origins"] = {
        item["snapshot"]: {"source": item["source"], "consumers": item["consumers"]}
        for snapshots in (entries, templates) for item in snapshots.values()
    }
    manifest["phase_one_file"] = "phase_one.py"
    manifest["phase_one_sha256"] = phase_one_sha256
    manifest["original_source"] = str(source)
    manifest["original_source_sha256"] = workflow.source_hash
    manifest["staged_input_nodes"] = {
        consumer["node_id"]: item["snapshot"]
        for item in entries.values()
        for consumer in item.get("consumers", ())
        if consumer.get("tool") == "Input Data" and consumer.get("node_id")
    }
    write_json(native / "manifest.json", manifest)
    plan = directory / "designer-plan.json"
    write_json(plan, [{"status": "ready", "workflow": str(staged), "run_dir": str(native)}])
    return {
        "status": "awaiting_designer",
        "runtime_input_dependencies": [
            node.node_id for node in workflow.nodes
            if node.tool_type in {"DynamicInput", "Directory"} or node.tool_type.startswith("Macro_")
        ],
        "designer_plan": str(plan), "native_workflow": str(native / manifest["instrumented_file"]),
        "answers": str(directory / "answers.json") if is_app else None,
        **({"log_event_ids": manifest["log_event_ids"]} if manifest.get("log_event_ids") else {}),
    }


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


def resume_migration(directory, *, native_outcome=None, failed_nodes=(), skipped_nodes=(), table_selection=None,
                     _verified_manifest=None):
    directory = directory.resolve()
    native = directory / "native"
    manifest = verify_manifest(native) if _verified_manifest is None else _verified_manifest
    if native_outcome:
        attest_native(native, native_outcome, failed_nodes=failed_nodes, skipped_nodes=skipped_nodes, _verified_manifest=manifest)
    attempt = 1
    destination = directory / "delivery"
    while destination.exists():
        attempt += 1
        destination = directory / f"delivery-{attempt}"
    result = verify_delivery(native, destination, observable=True, table_selection=table_selection, _verified_manifest=manifest)
    result["report"] = str(destination / "acceptance.json")
    return result


def launch_designer(directory, mode, pid, launcher=None):
    verify_manifest(directory / "native")
    if (directory / "answers.json").is_file():
        print(f"Using recorded App answers from {directory / 'answers.json'}.", file=sys.stderr, flush=True)
    return launch_designer_plan(directory / "designer-plan.json", directory / "designer-run.json", mode, pid, launcher)


def launch_designer_plan(plan, report, mode, pid=None, launcher=None, *, log=None, timeout=180):
    runner = Path(__file__).resolve().parents[2] / "scripts" / "designer_click_run.ps1"
    shell = shutil.which("pwsh")
    if shell is None or not runner.is_file():
        raise ValueError("Designer automation requires PowerShell 7 and the repository scripts directory")
    command = [
        shell, "-NoProfile", "-File", str(runner), "-Plan", str(plan),
        "-Report", str(report), "-AppLaunch", mode, "-ManualAppInputs", "-TimeoutSeconds", str(timeout),
    ]
    if pid:
        command.extend(["-DesignerProcessId", str(pid)])
    if launcher:
        command.extend(["-DesignerLauncher", str(launcher.resolve(strict=True))])
    previous = _report_signature(report)
    if log is None:
        result = subprocess.run(command, stdout=sys.stderr, check=False)
    else:
        with log.open("wb") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
    current = _report_signature(report)
    if current is None or current == previous:
        return {"status": "blocked", "returncode": result.returncode, "reason": "designer_report_unavailable",
                "detail": f"Designer did not publish a new run report: {report}"}
    return json.loads(report.read_text(encoding="utf-8-sig"))[0]


def _report_signature(report):
    try:
        stat = report.stat()
    except FileNotFoundError:
        return None
    return stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size
