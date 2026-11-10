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
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd

from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.tools.registry import TOOL_REGISTRY

from .snapshot import encode_value, frame_snapshot, compare_snapshots

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


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        self._warning_cursor = 0
        self._error_cursor = 0

    def record_node(self, **kwargs: Any) -> None:
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
            },
            "baseline": bool(kwargs["config"].get("baseline_semantics")),
            "warnings": self.warnings[self._warning_cursor :],
            "errors": self.errors[self._error_cursor :],
        }
        self._warning_cursor = len(self.warnings)
        self._error_cursor = len(self.errors)


def capture_python(
    workflow_path: Path, *, output_directory: Path | None = None
) -> dict:
    if output_directory is None:
        with tempfile.TemporaryDirectory(prefix="a2p-capture-") as directory:
            return _capture_python(workflow_path, Path(directory))
    output_directory.mkdir(parents=True, exist_ok=True)
    return _capture_python(workflow_path, output_directory)


def _capture_python(workflow_path: Path, output_directory: Path) -> dict:
    workflow = XmlWorkflowParser().parse(workflow_path)
    context = CaptureContext(
        runtime_config={"capture_output_dir": str(output_directory.resolve())}
    )
    failure = None
    blocked = False
    try:
        result = run_workflow_graph(workflow, context)
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
    for node in workflow.nodes:
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
    return {
        "source_sha256": file_hash(workflow_path),
        "producer": "python",
        "runtime_sha256": runtime_hash(),
        "status": "blocked" if blocked else "failed" if failure else "success",
        "failure": failure,
        "nodes": context.nodes,
        "warnings": context.warnings,
        "errors": context.errors,
        "environment": {
            "python": sys.version,
            "pandas": pd.__version__,
            "platform": platform.platform(),
            "locale": locale.setlocale(locale.LC_ALL),
            "timezone": list(time.tzname),
        },
    }


def prepare(workflow_path: Path, destination: Path) -> dict:
    workflow_path = workflow_path.resolve()
    workflow = XmlWorkflowParser().parse(workflow_path)
    unsupported = sorted(
        {
            node.tool_type
            for node in workflow.nodes
            if node.tool_type not in LOCAL_TOOLS
            and not node.tool_type.startswith("Macro_")
        }
    )
    if unsupported:
        raise ValueError(
            "Automatic node capture has no local adapter for: " + ", ".join(unsupported)
        )
    for node in workflow.nodes:
        if node.tool_type == "DbFileInput":
            path_value = str(node.config.get("normalized", {}).get("file", ""))
            raw_path = path_value.split("|||", 1)[0]
            path = Path(raw_path)
            if not path.is_absolute():
                path = workflow_path.parent / path
            if (
                "://" in raw_path
                or path.suffix.lower() not in {".csv", ".tsv", ".txt", ".xlsx", ".yxdb"}
                or not path.is_file()
            ):
                raise ValueError(
                    "Automatic capture supports existing local file inputs only"
                )
    # A new directory prevents accidentally reusing old native outputs.
    destination.mkdir(parents=True, exist_ok=False)
    destination = destination.resolve()
    tree = ET.parse(workflow_path)
    root = tree.getroot()
    nodes = root.find("Nodes")
    if nodes is None:
        raise ValueError("Workflow has no Nodes element")
    connections = root.find("Connections")
    if connections is None:
        connections = ET.SubElement(root, "Connections")
    next_id = max(int(node.attrib["ToolID"]) for node in root.iter("Node")) + 1
    probes = []
    for node in workflow.nodes:
        from alteryx2python.runtime.executor import _metadata_for_node

        metadata = _metadata_for_node(node, WorkflowContext())
        original_node = next(
            element
            for element in root.iter("Node")
            if element.get("ToolID") == node.node_id
        )
        if node.tool_type == "DbFileInput":
            file_node = original_node.find("Properties/Configuration/File")
            raw, marker, sheet = file_node.text.partition("|||")
            path = Path(raw)
            if not path.is_absolute():
                path = workflow_path.parent / path
            file_node.text = str(path.resolve()) + marker + sheet
        if node.tool_type == "DbFileOutput":
            file_node = original_node.find("Properties/Configuration/File")
            if file_node is None or not file_node.text:
                raise ValueError("Output sink is missing a file path")
            raw, marker, sheet = file_node.text.partition("|||")
            file_node.text = (
                str(destination / f"native-sink-{node.node_id}{Path(raw).suffix}")
                + marker
                + sheet
            )
        if node.tool_type.startswith("Macro_"):
            cfg = node.config.get("normalized", {})
            macro = Path(str(cfg.get("macro_path", "")))
            options = (
                [macro]
                if macro.is_absolute()
                else [
                    workflow_path.parent / macro,
                    Path("D:/Alteryx/bin/RuntimeData/Macros") / macro,
                ]
            )
            resolved = next((p.resolve() for p in options if p.is_file()), None)
            if resolved is None:
                raise ValueError("Macro dependency is unavailable for native capture")
            settings = original_node.find("EngineSettings")
            if settings is None:
                settings = original_node.find("Properties/EngineSettings")
            if settings is None:
                raise ValueError("Macro node has no native EngineSettings")
            settings.set("Macro", str(resolved))
        # Include disconnected anchors as well as those present in graph edges.
        anchors = set(metadata.output_anchors) | {
            anchor.name for anchor in node.output_anchors
        }
        if node.tool_type == "DbFileOutput":
            anchors = set()
        for anchor in sorted(anchors):
            filename = f"probe-{len(probes):04d}.yxdb"
            output_path = destination / filename
            probe_node = ET.SubElement(nodes, "Node", ToolID=str(next_id))
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
                    "file": filename,
                    "probe_id": str(next_id),
                }
            )
            next_id += 1
    # Pin original engine for the optional reader's supported format.
    properties = root.find("Properties")
    if properties is None:
        properties = ET.SubElement(root, "Properties")
    runtime = properties.find("RuntimeProperties")
    if runtime is None:
        runtime = ET.SubElement(properties, "RuntimeProperties")
    e2 = runtime.find("EnableEngine2")
    if e2 is None:
        e2 = ET.SubElement(runtime, "EnableEngine2")
    e2.set("value", "False")
    instrumented = destination / "instrumented.yxmd"
    tree.write(instrumented, encoding="utf-8", xml_declaration=True)
    manifest = {
        "source": str(workflow_path),
        "source_sha256": file_hash(workflow_path),
        "instrumented_sha256": file_hash(instrumented),
        "engine_mode": "original",
        "macro_dependencies_sha256": {},
        "probes": probes,
        "nodes": [
            {"node_id": node.node_id, "tool_type": node.tool_type}
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
        ],
    }
    from alteryx2python.generator.macro_sources import collect_macro_sources

    sources, missing_macros = collect_macro_sources(workflow)
    if missing_macros:
        raise ValueError(f"Macro dependencies unavailable: {missing_macros}")
    manifest["macro_dependencies_sha256"] = {
        path: file_hash(Path(path)) for path in sources
    }
    write_json(destination / "manifest.json", manifest)
    write_json(
        destination / "python.json",
        capture_python(workflow_path, output_directory=destination / "python-outputs"),
    )
    return manifest


def read_yxdb(path: Path) -> dict:
    try:
        from yxdb.yxdb_reader import YxdbReader
    except ImportError as exc:
        raise RuntimeError(
            "Install optional parity dependencies: pip install -e '.[parity]'"
        ) from exc
    # Own the stream so even reader-construction failures close the file.
    with path.open("rb") as stream:
        reader = YxdbReader(stream=stream)
        fields = reader.list_fields()
        meta = ET.fromstring(reader.meta_info_str)
        schema = [
            {key: field.get(key) for key in ("name", "type", "size", "scale")}
            for field in meta.findall("./RecordInfo/Field")
        ]
        if len(schema) != len(fields) or [field["name"] for field in schema] != [
            field.name for field in fields
        ]:
            raise ValueError("YXDB RecordInfo does not match decoded fields")
        rows = []
        while reader.next():
            rows.append(
                [encode_value(reader.read_index(index)) for index in range(len(fields))]
            )
        return {
            "columns": [field.name for field in fields],
            "schema": schema,
            "rows": rows,
        }


def verify_manifest(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if file_hash(Path(manifest["source"])) != manifest["source_sha256"]:
        raise ValueError("Source workflow changed after preparation")
    if file_hash(directory / "instrumented.yxmd") != manifest["instrumented_sha256"]:
        raise ValueError("Instrumented workflow changed after preparation")
    for path, digest in manifest.get("macro_dependencies_sha256", {}).items():
        if not Path(path).is_file() or file_hash(Path(path)) != digest:
            raise ValueError(f"Macro dependency changed after preparation: {path}")
    return manifest


def execute_native(directory: Path, engine: Path, timeout: float = 120) -> dict:
    verify_manifest(directory)
    if (directory / "native-run.json").exists() or any(directory.glob("probe-*.yxdb")):
        raise ValueError("Native artifacts already exist; prepare a new run directory")
    command = [str(engine.resolve()), str((directory / "instrumented.yxmd").resolve())]
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
                path.name: file_hash(path) for path in directory.glob("probe-*.yxdb")
            },
        }
    )
    write_json(directory / "native-run.json", result)
    return result


def collect_native(directory: Path, *, manual: bool = False) -> dict:
    manifest = verify_manifest(directory)
    run_path = directory / "native-run.json"
    review_path = directory / "manual-review.json"
    review = (
        json.loads(review_path.read_text(encoding="utf-8"))
        if review_path.exists()
        else None
    )
    if review is not None:
        if (
            review["source_sha256"] != manifest["source_sha256"]
            or review["instrumented_sha256"] != manifest["instrumented_sha256"]
        ):
            raise ValueError("Manual review references another workflow")
        for filename, digest in review["output_sha256"].items():
            if file_hash(directory / filename) != digest:
                raise ValueError("Native output changed after manual review")
        run = review
    elif run_path.exists():
        run = json.loads(run_path.read_text(encoding="utf-8"))
    elif manual:
        run = {"status": "incomplete", "reason": "manual_run_diagnostics_unavailable"}
    else:
        raise ValueError(
            "Missing native run record; use --manual after running in Designer"
        )
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
    for probe in manifest["probes"]:
        path = directory / probe["file"]
        if not path.exists():
            missing.append(probe)
            continue
        try:
            if run.get("output_sha256") is not None and run["output_sha256"].get(
                path.name
            ) != file_hash(path):
                raise ValueError("Native output changed after engine run")
            nodes[probe["node_id"]]["outputs"][probe["anchor"]] = read_yxdb(path)
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
            inputs[anchor] = output
    for node_id, node in nodes.items():
        if review is not None:
            node["status"] = review["node_outcomes"].get(node_id, "unknown")
        elif run["status"] == "success":
            expected = [
                probe for probe in manifest["probes"] if probe["node_id"] == node_id
            ]
            if all(probe["anchor"] in node["outputs"] for probe in expected):
                node["status"] = "success"
    return {
        "producer": "alteryx",
        "source_sha256": manifest["source_sha256"],
        "status": run["status"],
        "run": run,
        "nodes": nodes,
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


def compare_runs(native: dict, python: dict, *, profile: str = "behavioral") -> dict:
    if profile == "behavioral":
        from .behavior import compare_behavior_runs

        return compare_behavior_runs(native, python, runtime_hash())
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
