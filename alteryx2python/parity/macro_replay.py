"""Rebuild an actual macro call from attested native input streams."""

from copy import deepcopy
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from alteryx2python.workflow_generator import WorkflowBuilder, escape

from .amp_export import native_probe_path
from .runner import collect_native, file_hash, instrumented_path, prepare, verify_manifest, write_json
from .snapshot import compare_snapshots


def prepare_macro_replay(directory: Path, caller_id: str, destination: Path) -> dict:
    manifest = verify_manifest(directory)
    native = collect_native(directory)
    caller = native["nodes"].get(caller_id)
    if not caller or not caller["tool_type"].startswith("Macro_"):
        raise ValueError(f"Node {caller_id} is not a local macro call")
    if caller["status"] != "success" or not caller["outputs"]:
        raise ValueError(f"Macro {caller_id} needs successful native boundary evidence")

    parent = ET.parse(instrumented_path(directory, manifest)).getroot()
    original = parent.find(f".//Node[@ToolID='{caller_id}']")
    if original is None:
        raise ValueError(f"Instrumented workflow has no node {caller_id}")
    macro = deepcopy(original)
    probe_files = {
        (probe["node_id"], probe["anchor"]): probe["file"]
        for probe in manifest["probes"]
    }
    hashes = native["run"].get("output_sha256", {})
    connections = []
    builder = WorkflowBuilder(next_tool_id=int(caller_id) + 1)
    inputs = []
    for connection in parent.findall("Connections/Connection"):
        target, source = connection.find("Destination"), connection.find("Origin")
        if target is None or source is None or target.get("ToolID") != caller_id:
            continue
        source_name = (source.get("ToolID"), source.get("Connection"))
        filename = probe_files.get(source_name)
        if filename is None or filename not in hashes:
            raise ValueError(f"Missing attested input probe for macro {caller_id}: {source_name}")
        path = (directory / filename).resolve()
        if file_hash(path) != hashes[filename]:
            raise ValueError(f"Native input changed: {filename}")
        readable = native_probe_path(path)
        if hashes.get(readable.relative_to(directory.resolve()).as_posix()) != file_hash(readable):
            raise ValueError(f"Macro input is missing an attested readable export: {filename}")
        input_id = builder._node(
            "DbFileInput", f'<File FileFormat="19">{escape(readable)}</File>', (50, 50 + len(inputs) * 100)
        )
        edge = deepcopy(connection)
        edge.find("Origin").attrib.update(ToolID=str(input_id), Connection="Output")
        connections.append(edge)
        inputs.append({"source": source_name, "target": target.get("Connection"), "sha256": hashes[filename]})

    wrapper = ET.fromstring(builder.render())
    wrapper.find("Nodes").append(macro)
    wrapper.find("Connections").extend(connections)
    constants = parent.find("Properties/Constants")
    if constants is not None:
        wrapper.find("Properties").append(deepcopy(constants))
    destination.mkdir(parents=True, exist_ok=False)
    workflow_path = destination / "replay.yxmd"
    ET.ElementTree(wrapper).write(workflow_path, encoding="utf-8", xml_declaration=True)
    capture_dir = destination / "capture"
    prepare(workflow_path, capture_dir)

    python = json.loads((capture_dir / "python.json").read_text(encoding="utf-8"))
    actual = python["nodes"][caller_id]["outputs"]
    expected = caller["outputs"]
    comparisons = {
        anchor: compare_snapshots(expected[anchor], actual[anchor])
        if anchor in expected and anchor in actual
        else {"status": "incomplete", "reason": "missing_anchor"}
        for anchor in sorted(expected.keys() | actual.keys())
    }
    statuses = {diff["status"] for diff in comparisons.values()}
    status = python["status"] if python["status"] != "success" else (
        "match" if statuses == {"match"} else "mismatch" if "mismatch" in statuses else "incomplete"
    )
    report = {
        "status": status,
        "parent_source_sha256": manifest["source_sha256"],
        "caller_id": caller_id,
        "inputs": inputs,
        "comparisons": comparisons,
        "instrumented_workflow": str(capture_dir / "instrumented.yxmd"),
    }
    write_json(destination / "boundary-comparison.json", report)
    return report
