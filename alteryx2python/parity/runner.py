from __future__ import annotations

import hashlib
import json
import locale
import platform
import re
import subprocess
import sys
import time
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd

from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.runtime.scheduling import container_guards, detour_exclusions
from alteryx2python.tools.delivery import XLSX_PROFILE, xlsx_render_options
from alteryx2python.tools.registry import TOOL_REGISTRY

from .local_adapters import (
    bind_formula_clock, field_reference, formula_text, insert_input_formula, isolated_workbook_name,
    project_report_snapshot, report_projection_nodes, workbook_artifacts, workbook_digest,
)
from .snapshot import encode_value, frame_snapshot, compare_snapshots
from .checkpoints import anchor_stem

# Automated runs only support local, side-effect-free data processing here.
LOCAL_TOOLS = {
    "DbFileInput",
    "DbFileOutput",
    "TextInput",
    "Select",
    "Filter",
    "Formula",
    "Sort",
    "Sample",
    "Unique",
    "Join",
    "Union",
    "Summarize",
    "Transpose",
    "CrossTab",
    "RecordID",
    "RegEx",
    "TextToColumns",
    "DateTime",
    "AppendFields",
    "FieldInfo",
    "RunningTotal",
    "MultiRowFormula",
    "MultiFieldFormula",
    "GenerateRows",
    "AutoField",
    "BrowseV2",
    "CountRecords",
    "SelectRecords",
    "RandomRecords",
    "WeightedAvg",
    "Imputation",
    "Base64Encoder",
}

# Tools whose Python side deliberately executes external code, commands, or
# network traffic: excluded from automatic batch parity (the native side would
# run them too, but silent mass execution of arbitrary side effects is unsafe).
SIDE_EFFECT_TOOLS = {
    "RunCommand",
    "JupyterCode",
    "Download",
    "APIOutput",
    "DynamicInput",
    "BlobInput",
    "BlobOutput",
    "PortfolioComposerRender",
    "Email",
}


def _dynamic_local_tools() -> set[str]:
    """Whitelist = curated base + every registry tool with a real (non-baseline)
    Python implementation, minus side-effect tools."""
    real = {
        tool_type
        for tool_type in TOOL_REGISTRY.list_tool_types()
        if TOOL_REGISTRY.get(tool_type).maturity.startswith("L2")
    }
    return (LOCAL_TOOLS | real) - SIDE_EFFECT_TOOLS


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sink_digest(path: Path) -> str:
    return workbook_digest(path) if path.suffix.lower() == ".xlsx" else file_hash(path)


def file_artifacts(directory: Path) -> dict:
    return {
        path.relative_to(directory).as_posix(): file_hash(path)
        for path in sorted(directory.rglob("*")) if path.is_file()
    }


def native_sink_artifacts(directory: Path, manifest: dict) -> dict:
    return {
        node_id: file_hash(directory / filename)
        for node_id, filename in manifest.get("sink_files", {}).items()
        if (directory / filename).is_file()
    }


def native_render_artifacts(directory: Path, manifest: dict) -> dict:
    return {
        name: file_artifacts(directory / name)
        for name in manifest.get("render_folders", {}).values()
    }


def runtime_hash() -> str:
    package = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(p for p in package.rglob("*") if p.suffix in {".py", ".json"}):
        digest.update(path.relative_to(package).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


class CaptureContext(WorkflowContext):
    def __init__(self, runtime_config: dict[str, Any] | None = None) -> None:
        super().__init__(runtime_config=runtime_config)
        self.nodes: dict[str, Any] = {}
        self.macro_invocations: dict[str, dict[str, Any]] = {}
        self._warning_cursor = 0
        self._error_cursor = 0

    def macro_context(
        self, runtime_config: dict[str, Any], caller_id: str, invocation: int
    ) -> CaptureContext:
        child = CaptureContext(runtime_config)
        self.macro_invocations.setdefault(caller_id, {})[str(invocation)] = {
            "nodes": child.nodes,
            "macro_invocations": child.macro_invocations,
        }
        return child

    def record_node(self, **kwargs: Any) -> None:
        inactive_anchor = None
        if kwargs["tool_type"] == "Detour" and kwargs["status"] == "success":
            inactive_anchor = "Left" if kwargs["config"].get("detour_right") else "Right"
        super().record_node(**kwargs)
        self.nodes[str(kwargs["node_id"])] = {
            "tool_type": kwargs["tool_type"],
            "status": kwargs["status"],
            "inputs": {
                anchor: frame_snapshot(frame)
                for anchor, frame in kwargs["inputs"].items()
            },
            "outputs": {
                anchor: frame_snapshot(frame)
                for anchor, frame in kwargs["outputs"].items()
                if anchor != inactive_anchor
            },
            "baseline": bool(kwargs["config"].get("baseline_semantics")),
            "warnings": self.warnings[self._warning_cursor :],
            "errors": self.errors[self._error_cursor :],
        }
        if kwargs["status"] == "skipped":
            self.nodes[str(kwargs["node_id"])].update(
                skip_reason=kwargs["config"].get("reason"), inputs={}, outputs={}
            )
        self._warning_cursor = len(self.warnings)
        self._error_cursor = len(self.errors)


def capture_python(
    workflow_path: Path, *, output_directory: Path | None = None, answers: dict | None = None,
    event_commands: tuple[str, ...] = (), generated_entry=None, log_event_ids=(), render_folders=None, as_of=None,
    workflow=None, runtime_config=None, evidence_source_sha256=None,
) -> dict:
    workflow = XmlWorkflowParser().parse(workflow_path) if workflow is None else workflow
    options = dict(
        answers=answers, event_commands=event_commands, generated_entry=generated_entry, log_event_ids=log_event_ids,
        render_folders=render_folders, as_of=as_of, runtime_config=runtime_config,
        evidence_source_sha256=workflow.source_hash if evidence_source_sha256 is None else evidence_source_sha256,
    )
    if output_directory is None:
        with tempfile.TemporaryDirectory(prefix="a2p-capture-") as directory:
            return _capture_python(workflow, Path(directory), **options)
    output_directory.mkdir(parents=True, exist_ok=True)
    return _capture_python(workflow, output_directory, **options)


def _capture_python(
    workflow, output_directory: Path, *, answers, event_commands, generated_entry, log_event_ids,
    render_folders, as_of, runtime_config, evidence_source_sha256,
) -> dict:
    runtime = {**(runtime_config or {}), "capture_output_dir": str(output_directory.resolve()), "answers": answers}
    if as_of:
        runtime["as_of"] = as_of
    report_directory = output_directory / "render"
    if render_folders:
        runtime.update(delivery_profile=XLSX_PROFILE, output_dir=report_directory)
    if log_event_ids:
        runtime["log_event_ids"] = log_event_ids
    if event_commands:
        events_dir = output_directory / "events"
        events_dir.mkdir(exist_ok=False)
        runtime.update(allowed_commands=event_commands, event_working_dir=events_dir)
    context = CaptureContext(runtime_config=runtime)
    failure = None
    blocked = False
    try:
        result = (
            run_workflow_graph(workflow, context) if generated_entry is None else generated_entry(context=context)[0]
        )
        # Cover tools that return outputs but do not call record_node.
        for node_id, node in result.node_results.items():
            context.nodes.setdefault(
                node_id,
                {
                    "tool_type": node.tool_type,
                    "status": "success",
                    "inputs": {},
                    "outputs": {
                        anchor: frame_snapshot(frame)
                        for anchor, frame in node.outputs.items()
                    },
                    "baseline": False,
                    "warnings": None,
                    "errors": None,
                },
            )
    except Exception as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        blocked = (
            isinstance(
                exc, (ImportError, NotImplementedError, subprocess.TimeoutExpired)
            )
            or isinstance(exc.__cause__, ImportError)
            or type(exc).__name__ == "SnapshotEncodingError"
        )
    from alteryx2python.runtime.app_config import INTERFACE

    for node in workflow.nodes:
        if node.tool_type in INTERFACE and node.node_id not in context.nodes:
            continue
        context.nodes.setdefault(
            node.node_id,
            {
                "tool_type": node.tool_type,
                "status": "not_run",
                "inputs": {},
                "outputs": {},
                "baseline": False,
            },
        )
        if node.tool_type == "DbFileOutput":
            # The native sink has no outgoing data port. Its input is compared;
            # the Python compatibility Output return is not a native checkpoint.
            context.nodes[node.node_id]["outputs"] = {}
    source_identity = hashlib.sha256(workflow.source_file.encode()).hexdigest()[:12]
    if render_folders:
        workbooks = workbook_artifacts(report_directory)
        destinations = {
            name: label for item in context.diagnostics if item.get("kind") == "render_destinations"
            for name, label in item["paths"].items()
        }
        render_digests = {
            isolated_workbook_name(destinations[name]) if destinations.get(name) is not None else name: digest
            for name, digest in workbooks.items()
        }
        render_output_names = {
            isolated_workbook_name(destinations[name]) if destinations.get(name) is not None else name: name
            for name in workbooks
        }
    return {
        "source_sha256": evidence_source_sha256,
        "producer": "python",
        "answers": answers,
        "runtime_sha256": runtime_hash(),
        "status": "blocked" if blocked else "failed" if failure else "success",
        "failure": failure,
        "nodes": context.nodes,
        "macro_invocations": context.macro_invocations,
        "warnings": context.warnings,
        "errors": context.errors,
        "sink_artifacts": {
            path.stem.rsplit("-", 1)[-1]: sink_digest(path)
            for path in output_directory.glob(f"python-sink-{source_identity}-*")
            if path.is_file()
        },
        **({"event_artifacts": file_artifacts(events_dir)} if event_commands else {}),
        **({"workbooks": workbooks, "render_digests": render_digests,
            "render_output_names": render_output_names} if render_folders else {}),
        **({"workflow_logs": [item["record"] for item in context.diagnostics if item.get("kind") == "workflow_log"]}
           if log_event_ids else {}),
        "environment": {
            "python": sys.version,
            "pandas": pd.__version__,
            "platform": platform.platform(),
            "locale": locale.setlocale(locale.LC_ALL),
            "timezone": list(time.tzname),
        },
    }


def instrumented_path(directory: Path, manifest: dict) -> Path:
    return directory / manifest.get("instrumented_file", "instrumented.yxmd")


def prepare(
    workflow_path: Path, destination: Path, *, answers: dict | None = None,
    event_commands: tuple[str, ...] = (),
    capture_reference: bool = True, allow_missing_inputs: bool = False,
    instrumented_filename: str | None = None, log_event_ids=(),
    dynamic_inputs: dict | None = None, isolate_xlsx_render: bool = False, as_of=None,
) -> dict:
    workflow_path = workflow_path.resolve()
    workflow = XmlWorkflowParser().parse(workflow_path)
    is_app = workflow_path.suffix.lower() == ".yxwz"
    extension = ".yxwz" if is_app else ".yxmd"
    instrumented_name = Path(instrumented_filename or ("instrumented" + extension))
    if instrumented_name.parent != Path(".") or instrumented_name.suffix.lower() != extension:
        raise ValueError(f"Instrumented filename must be a local {extension} filename")
    if answers is not None and not is_app:
        raise ValueError("Explicit Designer answers require an analytic app (.yxwz)")
    from alteryx2python.runtime.app_config import INTERFACE
    from alteryx2python.workflow_events import bind_logging_events, workflow_events

    events = bind_logging_events(workflow_events(workflow.source_xml), log_event_ids)
    logging_ids = [event["id"] for event in events if event.get("kind") == "logging"]
    events = [event for event in events if event.get("kind") != "logging"]
    if events and not event_commands:
        raise ValueError("Automatic capture needs an isolated workflow event test case")
    programs = {}
    if events:
        allowed = {Path(command).resolve(strict=True) for command in event_commands}
        for event in events:
            if event.get("kind") == "email":
                raise ValueError("Email events need a test delivery adapter")
            program = (workflow_path.parent / event["program"]).resolve()
            if program not in allowed or not program.is_file():
                raise ValueError(f"Event executable is not allowed: {program}")
            programs[int(event["id"])] = program
    if is_app:
        workflow.nodes = [node for node in workflow.nodes if node.tool_type not in INTERFACE]
    # Canvas annotation tools (catalog gui_only entries) carry no data flow;
    # they document the canvas and must not block data parity capture.
    from alteryx2python.parser.tool_catalog import CATALOG as _CATALOG

    _gui_only = {entry.tool_type for entry in _CATALOG if entry.gui_only}
    _local_tools = _dynamic_local_tools()
    by_id = {node.node_id: node for node in workflow.nodes}
    static_skips = set() if is_app else {
        node.node_id for node in workflow.nodes if None in container_guards(node, by_id, ())
    }
    inactive_detours, detour_skips = (set(), set()) if is_app else detour_exclusions(workflow.nodes, workflow.edges)
    skip_reasons = {node_id: "container_disabled" for node_id in static_skips}
    skip_reasons.update({node_id: "detour_inactive" for node_id in detour_skips})
    static_skips = set(skip_reasons)
    dynamic_inputs = dynamic_inputs or {}
    renders = {
        node.node_id: xlsx_render_options(node.config["normalized"])
        for node in workflow.nodes if isolate_xlsx_render and node.tool_type == "PortfolioComposerRender"
        and node.node_id not in static_skips
    }
    if len(renders) > 1:
        raise ValueError("Automatic XLSX capture supports one Render tool per case")
    projected_nodes = report_projection_nodes(workflow, static_skips) if renders else set()
    unsupported = sorted(
        {
            node.tool_type
            for node in workflow.nodes
            if node.node_id not in static_skips
            and node.node_id not in dynamic_inputs and node.node_id not in renders
            and node.tool_type not in _local_tools
            and node.tool_type not in _gui_only
            and not node.tool_type.startswith("Macro_")
        }
    )
    if unsupported:
        raise ValueError(
            "Automatic node capture has no local adapter for: " + ", ".join(unsupported)
        )
    for node in workflow.nodes:
        if node.tool_type == "DbFileInput" and node.node_id not in static_skips:
            path_value = str(node.config.get("normalized", {}).get("file", ""))
            raw_path = path_value.split("|||", 1)[0]
            path = Path(raw_path)
            if not path.is_absolute():
                path = workflow_path.parent / path
            if (
                "://" in raw_path
                or path.suffix.lower() not in {".csv", ".tsv", ".txt", ".xlsx", ".yxdb"}
                or (not path.is_file() and (path.exists() or not allow_missing_inputs))
            ):
                raise ValueError(
                    "Automatic capture supports existing local file inputs only"
                )
    # A new directory prevents accidentally reusing old native outputs.
    destination.mkdir(parents=True, exist_ok=False)
    destination = destination.resolve()
    tree = ET.parse(workflow_path)
    root = tree.getroot()
    if as_of:
        bind_formula_clock(root, as_of)
    if programs or logging_ids:
        native_events = destination / "native-events"
        if programs:
            native_events.mkdir()
        saved_events = root.find("./Properties/Events")
        for index, event in enumerate(saved_events.findall("Event")):
            if str(index) in logging_ids:
                saved_events.remove(event)
                continue
            if index not in programs:
                continue
            for names, value in (
                (("cmd_Program", "Command", "ProgramName"), programs[index]),
                (("cmd_WorkingDir", "WorkingDir", "WorkingDirectory"), native_events),
            ):
                for name in names:
                    event.attrib.pop(name, None)
                    for element in event.findall(name):
                        event.remove(element)
                ET.SubElement(event, names[0]).text = str(value)
    nodes = root.find("Nodes")
    if nodes is None:
        raise ValueError("Workflow has no Nodes element")
    connections = root.find("Connections")
    if connections is None:
        connections = ET.SubElement(root, "Connections")
    next_id = max((int(node.attrib["ToolID"]) for node in root.iter("Node")), default=0) + 1
    placement = {
        child.attrib["ToolID"]: (parent, child)
        for parent in root.iter()
        if parent.tag in {"Nodes", "ChildNodes"}
        for child in parent.findall("Node")
    }
    probes = []
    input_hashes = {}
    sink_files = {}
    render_folders = {}
    from alteryx2python.generator.macro_sources import collect_macro_sources, resolve_macro_path
    from alteryx2python.parser.file_references import resolve_file_references

    for node in workflow.nodes:
        from alteryx2python.runtime.executor import _metadata_for_node

        siblings, original_node = placement[node.node_id]
        macro = node.config.get("normalized", {}).get("macro_path")
        if macro:
            resolved = resolve_macro_path(macro, workflow_path.parent)
            if resolved is None and node.node_id not in static_skips:
                raise ValueError(
                    f"Macro dependency is unavailable for native capture for {node.tool_type} "
                    f"(Tool ID {node.node_id}): {workflow_path.parent / macro}"
                )
            if resolved is not None:
                settings = original_node.find("EngineSettings")
                if settings is None:
                    settings = original_node.find("Properties/EngineSettings")
                if settings is None:
                    raise ValueError("Macro node has no native EngineSettings")
                settings.set("Macro", str(resolved))
        if node.tool_type in _gui_only or node.node_id in static_skips:
            continue
        metadata = _metadata_for_node(node, WorkflowContext())
        if node.tool_type == "Directory":
            resolve_file_references(original_node, workflow_path)
        if node.tool_type == "DbFileInput":
            file_node = original_node.find("Properties/Configuration/File")
            raw, marker, sheet = file_node.text.partition("|||")
            path = Path(raw)
            if not path.is_absolute():
                path = workflow_path.parent / path
            path = path.resolve()
            input_hashes[str(path)] = file_hash(path) if path.is_file() else None
            file_node.text = str(path) + marker + sheet
        if node.tool_type == "DbFileOutput":
            file_node = original_node.find("Properties/Configuration/File")
            if file_node is None or not file_node.text:
                raise ValueError("Output sink is missing a file path")
            multifile = original_node.find("Properties/Configuration/MultiFile")
            if multifile is not None and multifile.get("value", "False").lower() in {"true", "1"}:
                raise ValueError("Automatic capture requires fixed destination output files")
            raw, marker, sheet = file_node.text.partition("|||")
            filename = f"native-sink-{node.node_id}{Path(raw).suffix}"
            sink_files[node.node_id] = filename
            file_node.text = str(destination / filename) + marker + sheet
        if node.node_id in renders:
            filename, _, group, _ = renders[node.node_id]
            folder = destination / f"render-{node.node_id}"
            folder.mkdir()
            render_folders[node.node_id] = folder.name
            config = original_node.find("Properties/Configuration")
            output = config.find("OutputFile")
            if output is None:
                output = ET.SubElement(config, "OutputFile")
            output.text = str(folder / filename)
            temp_type = config.find("TempFileType")
            if temp_type is not None:
                temp_type.text = None
            if group:
                path_field = f"__a2p_render_path_{node.node_id}"
                prefix = formula_text(folder.as_posix() + "/report-")
                expression = f'{prefix} + MD5_UTF8({field_reference(group)}) + ".xlsx"'
                insert_input_formula(root, node.node_id, next_id, path_field, expression)
                next_id += 1
                config.find("GroupField").text = path_field
                config.find("FilenameModifier").text = "ReplacePath"
        # Include disconnected anchors as well as those present in graph edges.
        anchors = set(metadata.output_anchors) | {
            anchor.name for anchor in node.output_anchors
        }
        if node.tool_type == "DbFileOutput" or node.node_id in renders:
            anchors = set()
        for anchor_number, anchor in enumerate(sorted(anchors), 1):
            if (node.node_id, anchor) in inactive_detours:
                continue
            filename = f"{anchor_stem(node.node_id, anchor_number)}.yxdb"
            output_path = destination / filename
            probe_node = ET.SubElement(siblings, "Node", ToolID=str(next_id))
            gui = ET.SubElement(
                probe_node,
                "GuiSettings",
                Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
            )
            ET.SubElement(gui, "Position", x=str(150 + len(probes) * 60), y="600")
            properties = ET.SubElement(probe_node, "Properties")
            config = ET.SubElement(properties, "Configuration")
            ET.SubElement(config, "File", FileFormat="19", MaxRecords="").text = str(
                output_path
            )
            ET.SubElement(config, "Passwords")
            ET.SubElement(config, "FormatSpecificOptions")
            ET.SubElement(config, "MultiFile", value="False")
            ET.SubElement(
                probe_node,
                "EngineSettings",
                EngineDll="AlteryxBasePluginsEngine.dll",
                EngineDllEntryPoint="AlteryxDbFileOutput",
            )
            connection = ET.SubElement(connections, "Connection")
            ET.SubElement(connection, "Origin", ToolID=node.node_id, Connection=anchor)
            ET.SubElement(
                connection, "Destination", ToolID=str(next_id), Connection="Input"
            )
            probes.append(
                {
                    "node_id": node.node_id,
                    "anchor": anchor,
                    "anchor_number": anchor_number,
                    "file": filename,
                    "probe_id": str(next_id),
                }
            )
            next_id += 1
    properties = root.find("Properties")
    if properties is None:
        properties = ET.SubElement(root, "Properties")
    runtime = properties.find("RuntimeProperties")
    if runtime is None:
        runtime = ET.SubElement(properties, "RuntimeProperties")
    module_type = runtime.find("ModuleType")
    if not is_app and module_type is not None and module_type.text == "Standard":
        runtime.remove(module_type)
    e2 = runtime.find("EnableEngine2")
    if e2 is None:
        e2 = ET.SubElement(runtime, "EnableEngine2")
    amp = properties.find("RunWithE2")
    if amp is None:
        amp = ET.SubElement(properties, "RunWithE2")
    use_amp = any(
        flag.get("value", flag.text or "").lower() in {"true", "1"} for flag in (amp, e2)
    ) or any(node.tool_type == "ControlContainer" and node.node_id not in static_skips for node in workflow.nodes)
    for flag in (amp, e2):
        flag.set("value", str(use_amp))
    instrumented = destination / instrumented_name
    tree.write(instrumented, encoding="utf-8", xml_declaration=True)
    manifest = {
        "source": str(workflow_path),
        "source_sha256": file_hash(workflow_path),
        "instrumented_sha256": file_hash(instrumented),
        "instrumented_file": instrumented.name,
        "answers": answers,
        **({"as_of": as_of} if as_of else {}),
        "event_commands_sha256": {str(path): file_hash(path) for path in programs.values()},
        **({"log_event_ids": logging_ids} if logging_ids else {}),
        "inputs_sha256": input_hashes,
        "sink_files": sink_files,
        **({"dynamic_inputs": dynamic_inputs} if dynamic_inputs else {}),
        **({"render_folders": render_folders, "report_projection_nodes": sorted(projected_nodes)} if render_folders else {}),
        "engine_mode": "amp" if use_amp else "original",
        "macro_dependencies_sha256": {},
        "probes": probes,
        "nodes": [
            {
                "node_id": node.node_id,
                "tool_type": node.tool_type,
                **({"skip_reason": skip_reasons[node.node_id]} if node.node_id in static_skips else {}),
                **({"may_skip": True} if node.config.get("container_id") else {}),
                **({"no_data_output": True} if node.tool_type in _gui_only or node.tool_type in {"BrowseV2", "DbFileOutput"} or node.node_id in renders else {}),
            }
            for node in workflow.nodes
        ],
        "edges": [
            {
                "source": edge.source_node_id,
                "output": edge.source_anchor,
                "target": edge.target_node_id,
                "input": edge.target_anchor,
            }
            for edge in workflow.edges
            if edge.source_node_id in by_id and edge.target_node_id in by_id
            and edge.source_node_id not in detour_skips
            and (edge.source_node_id, edge.source_anchor) not in inactive_detours
        ],
    }
    enabled_nodes = [node for node in workflow.nodes if node.node_id not in static_skips]
    sources, missing_macros = collect_macro_sources(replace(workflow, nodes=enabled_nodes))
    if missing_macros:
        raise ValueError(f"Macro dependencies unavailable: {missing_macros}")
    for path, xml in sources.items():
        if workflow_events(xml):
            raise ValueError(f"Automatic capture needs an isolated workflow event test case: {path}")
        nested = XmlWorkflowParser().parse_xml(xml, Path(path))
        external = {node.tool_type for node in nested.nodes} & SIDE_EFFECT_TOOLS
        if external:
            raise ValueError(f"Automatic capture has no isolated macro adapter for: {', '.join(sorted(external))}")
    manifest["macro_dependencies_sha256"] = {
        path: file_hash(Path(path)) for path in sources
    }
    write_json(destination / "manifest.json", manifest)
    if capture_reference:
        write_json(
            destination / "python.json",
            capture_python(
                workflow_path, output_directory=destination / "python-outputs", answers=answers,
                event_commands=tuple(manifest["event_commands_sha256"]),
                log_event_ids=logging_ids,
                render_folders=render_folders,
                as_of=as_of,
            ),
        )
    return manifest


def read_yxdb(path: Path) -> dict:
    from alteryx2python.yxdb_file import read_yxdb_records

    schema, rows = read_yxdb_records(path)
    return {
        "columns": [field["name"] for field in schema],
        "schema": schema,
        "rows": [[encode_value(value) for value in row] for row in rows],
    }


def verify_manifest(directory: Path) -> dict:
    from .path_access import PathAccessError

    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if file_hash(Path(manifest["source"])) != manifest["source_sha256"]:
        raise ValueError("Source workflow changed after preparation")
    if file_hash(instrumented_path(directory, manifest)) != manifest["instrumented_sha256"]:
        raise ValueError("Instrumented workflow changed after preparation")
    for path, digest in manifest.get("macro_dependencies_sha256", {}).items():
        if not Path(path).is_file() or file_hash(Path(path)) != digest:
            raise ValueError(f"Macro dependency changed after preparation: {path}")
    for path, digest in manifest.get("event_commands_sha256", {}).items():
        if not Path(path).is_file() or file_hash(Path(path)) != digest:
            raise ValueError(f"Event executable changed after preparation: {path}")
    for path, digest in manifest.get("inputs_sha256", {}).items():
        origin = manifest.get("input_origins", {}).get(path, {})
        snapshot = Path(path)
        try:
            if digest is None and not snapshot.exists():
                continue
            actual = file_hash(snapshot)
        except OSError as error:
            raise PathAccessError("Read input snapshot", snapshot, error,
                                  consumers=origin.get("consumers", []), source=origin.get("source")) from error
        if actual != digest:
            raise ValueError(f"Input file changed after preparation: {path}")
    return manifest


def execute_native(directory: Path, engine: Path, timeout: float = 120) -> dict:
    manifest = verify_manifest(directory)
    if instrumented_path(directory, manifest).suffix.lower() == ".yxwz":
        raise ValueError("Run the analytic app in Designer with the recorded answers")
    probe_paths = [directory / probe["file"] for probe in manifest["probes"]]
    if (directory / "native-run.json").exists() or any(path.exists() for path in probe_paths):
        raise ValueError("Native artifacts already exist; prepare a new run directory")
    command = [str(engine.resolve()), str(instrumented_path(directory, manifest).resolve())]
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=timeout, check=False
        )
        raw = completed.stdout + completed.stderr
        result = {
            "status": "success" if completed.returncode in (0, 1) else "failed",
            "returncode": completed.returncode,
        }
    except subprocess.TimeoutExpired as exc:
        raw = (exc.stdout or b"") + (exc.stderr or b"")
        result = {"status": "blocked", "reason": "engine_timeout", "returncode": None}
    except OSError as exc:
        raw = str(exc).encode("utf-8")
        result = {"status": "blocked", "reason": str(exc), "returncode": None}
    (directory / "native-console.bin").write_bytes(raw)
    console = raw.decode("utf-8-sig", errors="replace")
    if re.search(
        r"not licensed|license.*(?:expired|unavailable)|no valid license", console, re.I
    ):
        result.update(status="blocked", reason="engine_license_unavailable")
    (directory / "native-console.txt").write_text(console, encoding="utf-8")
    result.update(
        {
            "command": command,
            "engine_sha256": file_hash(engine) if engine.is_file() else None,
            "console_sha256": hashlib.sha256(raw).hexdigest(),
            "output_sha256": {
                path.name: file_hash(path) for path in probe_paths if path.is_file()
            },
            **({"event_artifacts": file_artifacts(directory / "native-events")} if manifest.get("event_commands_sha256") else {}),
            **({"sink_artifacts": native_sink_artifacts(directory, manifest)} if manifest.get("sink_files") else {}),
            **({"render_artifacts": native_render_artifacts(directory, manifest)} if manifest.get("render_folders") else {}),
        }
    )
    write_json(directory / "native-run.json", result)
    return result


def _without_probe_messages(snapshot: dict, probe_paths: dict[str, Path]) -> tuple[dict, list]:
    if snapshot["columns"] != ["ToolID", "MessageType", "Message"]:
        return snapshot, []
    kept, removed = [], []
    for row in snapshot["rows"]:
        tool_id, severity, message = row
        path = probe_paths.get(tool_id.get("value")) if tool_id["kind"] == "int" else None
        text = message.get("value", "") if message["kind"] == "string" else ""
        emitted_path, separator, _ = text.partition("|")
        if path and severity == {"kind": "string", "value": "FileOutput"} and separator and Path(emitted_path) == path:
            removed.append(row)
        else:
            kept.append(row)
    return {**snapshot, "rows": kept}, removed


def collect_native(directory: Path, *, manual: bool = False, capture_report_fields: bool = False,
                   _verified_manifest: dict | None = None) -> dict:
    from .amp_export import native_probe_path

    manifest = verify_manifest(directory) if _verified_manifest is None else _verified_manifest
    run_path = directory / "native-run.json"
    review_path = directory / "manual-review.json"
    automatic_path = directory / "designer-evidence.json"
    review = (
        json.loads(review_path.read_text(encoding="utf-8"))
        if review_path.exists()
        else json.loads(automatic_path.read_text(encoding="utf-8")) if automatic_path.exists() else None
    )
    if review is not None:
        if (
            review["source_sha256"] != manifest["source_sha256"]
            or review["instrumented_sha256"] != manifest["instrumented_sha256"]
            or review.get("answers") != manifest.get("answers")
        ):
            raise ValueError("Designer evidence references another workflow")
        for filename, digest in review["output_sha256"].items():
            if file_hash(directory / filename) != digest:
                raise ValueError("Native output changed after Designer evidence was recorded")
        run = review
    elif run_path.exists():
        run = json.loads(run_path.read_text(encoding="utf-8"))
    elif manual:
        run = {"status": "incomplete", "reason": "manual_run_diagnostics_unavailable"}
    else:
        raise ValueError(
            "Missing native run record; use --manual after running in Designer"
        )
    if manifest.get("event_commands_sha256") and "event_artifacts" in run:
        if run["event_artifacts"] != file_artifacts(directory / "native-events"):
            raise ValueError("Native event artifacts changed after the run")
    if manifest.get("sink_files") and "sink_artifacts" in run:
        if run["sink_artifacts"] != native_sink_artifacts(directory, manifest):
            raise ValueError("Native sink artifacts changed after the run")
    if manifest.get("render_folders") and "render_artifacts" in run:
        if run["render_artifacts"] != native_render_artifacts(directory, manifest):
            raise ValueError("Native Render artifacts changed after the run")
    console_path = directory / "native-console.txt"
    console = console_path.read_text(encoding="utf-8") if console_path.exists() else ""
    # Raw console messages do not establish complete per-node diagnostics.
    # Leave those unknown until a versioned structured diagnostic adapter exists.
    nodes = {
        node["node_id"]: {
            "tool_type": node["tool_type"],
            "outputs": {},
            "inputs": {},
            "status": "unknown",
            "errors": None,
            "warnings": None,
        }
        for node in manifest["nodes"]
    }
    missing, unreadable = [], []
    capture_files = {node_id: {"inputs": {}, "outputs": {}} for node_id in nodes}
    input_sources = {}
    report_snapshots = {}
    probe_paths = {
        str(probe["probe_id"]): (directory / probe["file"]).resolve()
        for probe in manifest["probes"] if probe.get("probe_id") is not None
    }
    attested_skips = set(review.get("skipped_nodes", [])) if review else set()
    for probe in manifest["probes"]:
        path = directory / probe["file"]
        if not path.exists():
            if probe["node_id"] not in attested_skips:
                missing.append(probe)
            continue
        try:
            if review is None and run.get("output_sha256") is not None and run["output_sha256"].get(
                path.name
            ) != file_hash(path):
                raise ValueError("Native output changed after engine run")
            if review is not None and path.name not in review["output_sha256"]:
                raise ValueError("Native output was not recorded in Designer evidence")
            readable_path = native_probe_path(path)
            if review is not None and readable_path != path:
                if readable_path.relative_to(directory).as_posix() not in review["output_sha256"]:
                    raise ValueError("Classic export was not attested with its AMP probe")
            node = nodes[probe["node_id"]]
            snapshot = read_yxdb(readable_path)
            if node["tool_type"] == "ControlContainer" and probe["anchor"] == "Log":
                snapshot, removed = _without_probe_messages(snapshot, probe_paths)
                if removed:
                    node["excluded_probe_log_rows"] = removed
            if probe["node_id"] in manifest.get("report_projection_nodes", ()):
                if capture_report_fields:
                    report_snapshots[probe["node_id"], "outputs", probe["anchor"]] = snapshot
                snapshot = project_report_snapshot(snapshot)
            node["outputs"][probe["anchor"]] = snapshot
            capture_files[probe["node_id"]]["outputs"][probe["anchor"]] = readable_path.relative_to(directory).as_posix()
        except Exception as exc:
            unreadable.append({**probe, "error": str(exc)})
    # A node's native input is the upstream output on that exact connection.
    for edge in manifest["edges"]:
        output = nodes[edge["source"]]["outputs"].get(edge["output"])
        if output is not None:
            inputs = nodes[edge["target"]]["inputs"]
            anchor = edge["input"]
            suffix = 2
            while anchor in inputs:
                anchor = f"{edge['input']}_{suffix}"
                suffix += 1
            inputs[anchor] = (
                project_report_snapshot(output) if edge["target"] in manifest.get("report_projection_nodes", ())
                else output
            )
            if capture_report_fields:
                raw = report_snapshots.get((edge["source"], "outputs", edge["output"]), output)
                if raw is not inputs[anchor]:
                    report_snapshots[edge["target"], "inputs", anchor] = raw
            capture_files[edge["target"]]["inputs"][anchor] = capture_files[edge["source"]]["outputs"][edge["output"]]
            input_sources.setdefault(edge["target"], {})[anchor] = {
                "node_id": edge["source"], "anchor": edge["output"],
            }
    # Engine console lines attribute failures to nodes ("ToolId 5: ... Error").
    # Only the fact of failure is used (never the message text) so parity
    # matches behaviour, not wording.
    console_failed_nodes = set()
    for line in console.splitlines():
        match = re.match(r"\s*ToolId (\d+):.*\bError\b", line, re.I)
        if match:
            console_failed_nodes.add(match.group(1))
    workflow_failed = run.get("status") == "failed" or (
        review is not None and review.get("status") == "failed"
    )
    for definition in manifest["nodes"]:
        node_id = definition["node_id"]
        node = nodes[node_id]
        if node_id in console_failed_nodes:
            node["status"] = "failed"
            node["failure_source"] = "engine_error"
            continue
        if definition.get("skip_reason") or node_id in attested_skips:
            node.update(status="skipped", skip_reason=definition.get("skip_reason", "designer_observed"), inputs={})
            continue
        if review is not None:
            node["status"] = review["node_outcomes"].get(node_id, "unknown")
        elif run["status"] == "success":
            expected = [
                probe for probe in manifest["probes"] if probe["node_id"] == node_id
            ]
            if all(probe["anchor"] in node["outputs"] for probe in expected):
                node["status"] = "success"
        # A failed workflow never wrote these probes: the node demonstrably
        # produced no output, which is itself the behaviour to compare.
        if (workflow_failed and not (review and review.get("method") == "designer_automation")
                and node["status"] == "unknown" and not node["outputs"]):
            node["status"] = "failed"
            node["failure_source"] = "no_probe_written"
        if not node["outputs"] and node["status"] == "success" and not (
            definition.get("no_data_output") or node["tool_type"] == "DbFileOutput" and node["inputs"]
        ):
            node["status"] = "unknown"
    render_workbooks = {
        node_id: workbook_artifacts(directory / folder)
        for node_id, folder in manifest.get("render_folders", {}).items()
    } if "render_artifacts" in run else None
    sink_artifacts = {
        node_id: sink_digest(directory / manifest["sink_files"][node_id])
        for node_id in run["sink_artifacts"]
    } if manifest.get("sink_files") and "sink_artifacts" in run else None
    return {
        "producer": "alteryx",
        "source_sha256": manifest["source_sha256"],
        "answers": manifest.get("answers"),
        **({"event_artifacts": run.get("event_artifacts")} if manifest.get("event_commands_sha256") else {}),
        **({"sink_artifacts": sink_artifacts} if manifest.get("sink_files") else {}),
        **({"render_workbooks": render_workbooks, "render_digests": (
            next(iter(render_workbooks.values())) if render_workbooks else None
        )} if manifest.get("render_folders") else {}),
        "status": run["status"],
        "run": run,
        "nodes": nodes,
        "capture_files": capture_files,
        "input_sources": input_sources,
        **({"report_snapshots": report_snapshots} if capture_report_fields else {}),
        "missing": missing,
        "unreadable": unreadable,
        "errors": [
            line for line in console.splitlines() if re.match(r"\s*Error\b", line, re.I)
        ]
        if console
        else None,
        "warnings": [
            line
            for line in console.splitlines()
            if re.match(r"\s*Warning\b", line, re.I)
        ]
        if console
        else None,
        "raw_designer_messages": (
            (directory / "designer-messages.txt").read_text(encoding="utf-8")
            if (directory / "designer-messages.txt").exists()
            else None
        ),
    }


def compare_runs(native: dict, python: dict, *, profile: str = "behavioral", align_checkpoints: bool = False,
                 presentation_policy=None) -> dict:
    if profile == "behavioral":
        from .behavior import compare_behavior_runs

        return compare_behavior_runs(native, python, runtime_hash(), align_checkpoints=align_checkpoints,
                                     presentation_policy=presentation_policy)
    if profile != "strict":
        raise ValueError(f"Unknown comparison profile: {profile}")
    issues = []
    incomplete_evidence = []
    if native.get("source_sha256") != python.get("source_sha256"):
        issues.append("source_hash_mismatch")
    if native.get("producer") != "alteryx" or python.get("producer") != "python":
        issues.append("invalid_producer")
    if python.get("runtime_sha256") != runtime_hash():
        issues.append("python_runtime_changed_or_unrecorded")
    for dimension in ("errors", "warnings"):
        if native.get(dimension) is None or python.get(dimension) is None:
            incomplete_evidence.append(f"global_{dimension}_unverified")
        elif native[dimension] != python[dimension]:
            issues.append(f"{dimension}_mismatch")
    comparisons = []
    for node_id in sorted(set(native["nodes"]) | set(python["nodes"])):
        left = native["nodes"].get(node_id)
        right = python["nodes"].get(node_id)
        if left is None or right is None:
            comparisons.append(
                {"node_id": node_id, "status": "incomplete", "reason": "missing_node"}
            )
            continue
        if left["tool_type"] != right["tool_type"]:
            issues.append(f"node_{node_id}_tool_type_mismatch")
        if right.get("baseline"):
            issues.append(f"node_{node_id}_baseline")
        for dimension in ("status", "errors", "warnings"):
            if left.get(dimension) in (None, "unknown") or right.get(dimension) in (
                None,
                "unknown",
            ):
                incomplete_evidence.append(f"node_{node_id}_{dimension}_unverified")
            elif left[dimension] != right[dimension]:
                issues.append(f"node_{node_id}_{dimension}_mismatch")
        for direction in ("inputs", "outputs"):
            for anchor in sorted(set(left[direction]) | set(right[direction])):
                expected = left[direction].get(anchor)
                actual = right[direction].get(anchor)
                diff = (
                    {"status": "incomplete", "reason": "missing_anchor"}
                    if expected is None or actual is None
                    else compare_snapshots(expected, actual, profile="strict")
                )
                comparisons.append(
                    {
                        "node_id": node_id,
                        "direction": direction,
                        "anchor": anchor,
                        **diff,
                    }
                )
    statuses = {item["status"] for item in comparisons}
    if native["status"] == "blocked":
        status = "blocked"
    elif issues or "mismatch" in statuses:
        status = "mismatch"
    elif (
        native["status"] != "success"
        or python["status"] != "success"
        or native.get("missing")
        or native.get("unreadable")
        or incomplete_evidence
        or "incomplete" in statuses
        or not comparisons
    ):
        status = "incomplete"
    else:
        status = "match"
    return {
        "status": status,
        "universal_equivalence_proven": False,
        "native_status": native["status"],
        "python_status": python["status"],
        "issues": issues,
        "incomplete_evidence": incomplete_evidence,
        "comparisons": comparisons,
        "missing_native_outputs": native.get("missing", []),
        "unreadable_native_outputs": native.get("unreadable", []),
    }
