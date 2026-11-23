"""Use Designer to export AMP probe files as classic YXDB for comparison."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

AMP_HEADER = b"Alteryx e2 Database file"
EXPORT_DIR = "classic-export"


def _is_amp(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(len(AMP_HEADER)) == AMP_HEADER


def _file_tool(nodes, node_id, name, path, x, y):
    node = ET.SubElement(nodes, "Node", ToolID=str(node_id))
    gui = ET.SubElement(node, "GuiSettings", Plugin=f"AlteryxBasePluginsGui.{name}.{name}")
    ET.SubElement(gui, "Position", x=str(x), y=str(y))
    config = ET.SubElement(ET.SubElement(node, "Properties"), "Configuration")
    ET.SubElement(config, "File", FileFormat="19").text = str(path)
    ET.SubElement(config, "Passwords")
    ET.SubElement(config, "FormatSpecificOptions")
    ET.SubElement(node, "EngineSettings", EngineDll="AlteryxBasePluginsEngine.dll",
                  EngineDllEntryPoint=f"Alteryx{name}")


def prepare_amp_export(directory: Path, *, names=None, destination=None, _manifest=None) -> dict:
    from .runner import file_hash, verify_manifest, write_json

    directory = directory.resolve()
    manifest = verify_manifest(directory) if _manifest is None else _manifest
    names = names if names is not None else [
        probe["file"] for probe in manifest["probes"]
        if (directory / probe["file"]).is_file() and _is_amp(directory / probe["file"])
    ]
    if not names:
        raise ValueError("No AMP probe exports are available")
    destination = destination or directory / EXPORT_DIR
    destination.mkdir(exist_ok=False)
    original = ET.parse(directory / manifest["instrumented_file"]).getroot()
    root = ET.Element("AlteryxDocument", original.attrib)
    nodes = ET.SubElement(root, "Nodes")
    connections = ET.SubElement(root, "Connections")
    ET.SubElement(ET.SubElement(root, "Properties"), "RunWithE2", value="False")
    for index, name in enumerate(names):
        source_id, sink_id = 2 * index + 1, 2 * index + 2
        _file_tool(nodes, source_id, "DbFileInput", directory / name, 70, 70 + 80 * index)
        _file_tool(nodes, sink_id, "DbFileOutput", destination / name, 220, 70 + 80 * index)
        edge = ET.SubElement(connections, "Connection")
        ET.SubElement(edge, "Origin", ToolID=str(source_id), Connection="Output")
        ET.SubElement(edge, "Destination", ToolID=str(sink_id), Connection="Input")
    export_id = sha256(str(directory).encode("utf-8")).hexdigest()[:12]
    workflow = destination / f"export-classic-{export_id}.yxmd"
    ET.ElementTree(root).write(workflow, encoding="utf-8", xml_declaration=True)
    write_json(destination / "manifest.json", {
        "instrumented_file": workflow.name,
        "instrumented_sha256": file_hash(workflow),
        "source_probe_hashes": {name: file_hash(directory / name) for name in names},
        "macro_dependencies_sha256": {},
        "probes": [{"file": name} for name in names],
    })
    return {"workflow": str(workflow), "status": "ready", "run_dir": str(destination)}


def native_probe_path(path: Path) -> Path:
    from .runner import file_hash

    if not _is_amp(path):
        return path
    destination = path.parent / EXPORT_DIR
    index = destination / "batches.json"
    if index.is_file():
        batch = json.loads(index.read_text(encoding="utf-8")).get(path.name)
        if batch:
            destination = path.parent / batch
    receipt = destination / "manifest.json"
    if not receipt.is_file():
        raise ValueError("AMP YXDB requires a Designer classic export")
    manifest = json.loads(receipt.read_text(encoding="utf-8"))
    if manifest["source_probe_hashes"].get(path.name) != file_hash(path):
        raise ValueError(f"AMP input changed since classic export preparation: {path.name}")
    if file_hash(destination / manifest["instrumented_file"]) != manifest["instrumented_sha256"]:
        raise ValueError("Classic export workflow changed")
    converted = destination / path.name
    if converted.is_file() and _is_amp(converted):
        raise ValueError(f"Classic export is still AMP: {path.name}")
    return converted
