"""Place captured Designer and standalone Python artifacts in one review folder."""

import json
from pathlib import Path, PureWindowsPath
import shutil

from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.app_config import prepare_workflow

from .runner import file_hash, native_render_artifacts, native_sink_artifacts, verify_manifest


def _copy_output(source, destination):
    if not source or not source.is_file():
        return None
    digest = file_hash(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and file_hash(destination) != digest:
        destination = destination.with_name(f"{destination.stem}-{digest[:12]}{destination.suffix}")
    if not destination.exists():
        with source.open("rb") as source_file, destination.open("xb") as destination_file:
            shutil.copyfileobj(source_file, destination_file)
    return destination


def _render_names(capture):
    if "render_output_names" in capture:
        return capture["render_output_names"]
    # Earlier captures stored both filename-to-digest indexes.
    names = {}
    for native_name, digest in capture.get("render_digests", {}).items():
        candidates = [name for name, observed in capture.get("workbooks", {}).items() if observed == digest]
        if len(candidates) == 1:
            names[native_name] = candidates[0]
    return names


def build_output_comparison(native, delivery):
    manifest = verify_manifest(native)
    for name in ("manual-review.json", "designer-evidence.json", "native-run.json"):
        receipt = native / name
        if receipt.is_file():
            evidence = json.loads(receipt.read_text(encoding="utf-8"))
            for key, inspect in (("sink_artifacts", native_sink_artifacts), ("render_artifacts", native_render_artifacts)):
                if key in evidence and evidence[key] != inspect(native, manifest):
                    raise ValueError("Alteryx output changed after its recorded comparison")
            break
    outputs = delivery / "delivery-output"
    phase_one = delivery / "phase-one-output"
    comparison = delivery / "side-by-side"
    configured = prepare_workflow(XmlWorkflowParser().parse(Path(manifest["source"])), manifest.get("answers"))
    nodes = {node.node_id: node.config["normalized"] for node in configured.nodes}
    rows = []
    used_python = set()

    def add(node_id, filename, designer, python, fallback=None):
        phase = 2
        if python and python.is_file():
            used_python.add(python)
        elif fallback and fallback.is_file():
            python = fallback
            phase = 1
        context = Path(f"node-{node_id}") if node_id else Path("unpaired")
        designer_copy = _copy_output(designer, comparison / "Alteryx" / context / f"Alteryx - {filename}")
        label = "Python" if phase == 2 else "Python Phase 1"
        python_copy = _copy_output(python, comparison / "Python" / context / f"{label} - {filename}")
        if designer_copy or python_copy:
            rows.append({"node_id": node_id, "name": filename, "alteryx": designer_copy,
                         "python": python_copy, "python_phase": phase})

    for node_id, filename in manifest.get("sink_files", {}).items():
        basename = PureWindowsPath(nodes[node_id]["file"].partition("|||")[0]).name
        saved = next(phase_one.glob(f"python-sink-*-{node_id}{Path(filename).suffix}"), None)
        add(node_id, basename, native / filename, outputs / basename, saved)

    first = delivery / "phase-one-capture.json"
    capture = json.loads(first.read_text(encoding="utf-8")) if first.is_file() else {}
    render_names = _render_names(capture)
    for node_id, folder in manifest.get("render_folders", {}).items():
        designer_files = {path.name: path for path in (native / folder).glob("*.xlsx") if path.is_file()}
        if len(designer_files) == len(render_names) == 1:
            # A different name is still useful to review when this tool wrote one workbook on each side.
            native_name = next(iter(designer_files))
            python_name = next(iter(render_names.values()))
            render_names = {native_name: python_name}
        # Pair using the Render group identity, even when workbook contents differ.
        for name in sorted(designer_files.keys() | render_names.keys()):
            basename = render_names.get(name, name)
            add(node_id, basename, designer_files.get(name), outputs / basename, phase_one / "render" / basename)
    for path in sorted(outputs.glob("*")):
        if path.is_file() and path not in used_python:
            add(None, path.name, None, path)
    return rows
