"""Snapshot local macro configuration dependencies for generated Python."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET


def resolve_macro_path(raw, base, embedded=()):
    path = Path(raw)
    roots = (Path(base), Path("D:/Alteryx/bin/RuntimeData/Macros"), Path("D:/Alteryx/bin/HtmlPlugins"))
    candidates = (path,) if path.is_absolute() else (root / path for root in roots)
    for candidate in candidates:
        selected = candidate.resolve()
        if selected.is_file() or str(selected) in embedded:
            return selected
    return None


def ordered_macro_outputs(root):
    """Accept an explicit contract or an independently inspected macro fingerprint."""
    import hashlib
    canonical = ET.canonicalize(ET.tostring(root, encoding='unicode'), strip_text=True)
    known = {'d7b8752d20427d7280203de7c8591a2f3aeb9d5f18c5581f8c5ae7c88e80183d'}
    if root.findtext('Properties/MetaInfo/MigrationContract') != 'ordered-outputs-v1' and hashlib.sha256(canonical.encode()).hexdigest() not in known:
        return []
    return [node.findtext('Properties/Configuration/Name', 'Output') for node in root.iter('Node')
            if node.find('GuiSettings') is not None and 'MacroOutput' in node.find('GuiSettings').get('Plugin', '')]


def attach_macro_ordering(workflow, embedded, *, tolerate_unreadable=False):
    for node in workflow.nodes:
        if not node.tool_type.startswith('Macro_'):
            continue
        cfg = node.config.get('normalized', node.config)
        path = resolve_macro_path(cfg.get('macro_path', ''), cfg.get('base_dir', '.'), embedded)
        if path is not None:
            try:
                root = ET.fromstring(embedded[str(path)]) if str(path) in embedded else ET.parse(path).getroot()
            except (OSError, ET.ParseError):
                if tolerate_unreadable:
                    continue
                raise
            outputs = ordered_macro_outputs(root)
            if outputs:
                node.metadata['ordered_macro_outputs'] = outputs


def collect_macro_sources(workflow):
    from alteryx2python.tools.wait import is_crew_wait_macro

    sources, missing = {}, []

    def visit(raw, base):
        if is_crew_wait_macro(raw):
            return
        selected = resolve_macro_path(raw, base)
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
