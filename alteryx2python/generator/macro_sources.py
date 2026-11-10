"""Snapshot local macro configuration dependencies for generated Python."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET


def collect_macro_sources(workflow):
    sources, missing = {}, []

    def visit(raw, base):
        path = Path(raw)
        candidates = (
            [path]
            if path.is_absolute()
            else [base / path, Path("D:/Alteryx/bin/RuntimeData/Macros") / path]
        )
        selected = next((p.resolve() for p in candidates if p.is_file()), None)
        if selected is None:
            missing.append(str(base / raw))
            return
        key = str(selected)
        if key in sources:
            return
        root = ET.parse(selected).getroot()
        sources[key] = ET.tostring(root, encoding="unicode")
        for settings in root.iter("EngineSettings"):
            if settings.get("Macro"):
                visit(settings.get("Macro"), selected.parent)

    for node in workflow.nodes:
        config = node.config.get("normalized", {})
        if config.get("macro_path"):
            visit(
                str(config["macro_path"]),
                Path(str(config.get("base_dir", Path(workflow.source_file).parent))),
            )
    return sources, missing
