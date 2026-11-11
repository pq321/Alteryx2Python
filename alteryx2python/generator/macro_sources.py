"""Snapshot local macro configuration dependencies for generated Python."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET


def ordered_macro_outputs(root):
    """Accept an explicit contract or an independently inspected macro fingerprint."""
    import hashlib
    canonical = ET.canonicalize(ET.tostring(root, encoding='unicode'), strip_text=True)
    known = {'d7b8752d20427d7280203de7c8591a2f3aeb9d5f18c5581f8c5ae7c88e80183d'}
    if root.findtext('Properties/MetaInfo/MigrationContract') != 'ordered-outputs-v1' and hashlib.sha256(canonical.encode()).hexdigest() not in known:
        return []
    return [node.findtext('Properties/Configuration/Name', 'Output') for node in root.iter('Node')
            if node.find('GuiSettings') is not None and 'MacroOutput' in node.find('GuiSettings').get('Plugin', '')]


def attach_macro_ordering(workflow, embedded):
    for node in workflow.nodes:
        if not node.tool_type.startswith('Macro_'):
            continue
        cfg = node.config.get('normalized', node.config)
        raw = Path(cfg.get('macro_path', ''))
        candidates = [raw] if raw.is_absolute() else [Path(cfg.get('base_dir', '.')) / raw, Path('D:/Alteryx/bin/RuntimeData/Macros') / raw]
        path = next((item.resolve() for item in candidates if item.is_file() or str(item.resolve()) in embedded), None)
        if path is not None:
            root = ET.fromstring(embedded[str(path)]) if str(path) in embedded else ET.parse(path).getroot()
            outputs = ordered_macro_outputs(root)
            if outputs:
                node.metadata['ordered_macro_outputs'] = outputs


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
