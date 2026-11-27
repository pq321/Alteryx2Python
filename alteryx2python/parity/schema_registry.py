"""Inventory the configuration facts exposed by an installed Designer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
import shutil
import subprocess
from xml.etree import ElementTree as ET

from alteryx2python.parser.tool_catalog import CATALOG
from alteryx2python.parser.xml_parser import _normalize_macro_tool_type, _normalize_tool_type
from alteryx2python.runtime.app_config import question_manifest

from .runner import file_hash, write_json
from .scope import PALETTE_SCOPE

AMP_SENSITIVE = frozenset({
    "Sort", "Rank", "Unique", "CrossTab", "Tile", "FuzzyMatch", "Join",
    "JoinMultiple", "Union", "AppendFields", "Summarize", "CreateSamples",
    "RandomRecords", "Sample",
})

# Bind the CLR enum to the actual XML key used in the plugin's serializer.
# Member values come from the installed binary.
MANAGED_ENUMS = {
    "Union": (
        "Configuration/AutoResetMode",
        "AlteryxBasePluginsGui.dll",
        "AlteryxBasePluginsGui.Union.Configure+E_AutoResetModes",
    ),
}


@dataclass
class ToolConfigSchema:
    tool_type: str
    category: str
    engine_tier: str
    axes: dict[str, dict] = field(default_factory=dict)
    anchors: dict[str, list[dict]] = field(default_factory=dict)
    sources: set[str] = field(default_factory=set)
    engine_bindings: dict[str, dict] = field(default_factory=dict)
    macro_questions: dict[str, list[dict]] = field(default_factory=dict)
    macro_actions: dict[str, list[dict]] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)

    def observe(self, axis: str, value: str, *, legal_values=()) -> None:
        entry = self.axes.setdefault(axis, {"observed": set(), "declared": set()})
        if value:
            entry["observed"].add(value)
        entry["declared"].update(legal_values)

    def to_dict(self) -> dict:
        result = asdict(self)
        result["axes"] = {
            path: {kind: sorted(values) for kind, values in axis.items()}
            for path, axis in sorted(self.axes.items())
        }
        result["sources"] = sorted(self.sources)
        return result


_TOKEN = re.compile(r"[A-Za-z0-9_. +\-]{1,64}\Z")
_INSTANCE_TAGS = {"r", "c", "Record", "Row", "Cell", "Data", "Passwords"}
_INSTANCE_ATTRIBUTES = {"name", "field", "rename", "expression", "description"}


def _observe_xml(schema: ToolConfigSchema, element: ET.Element, path: str) -> None:
    # XML examples establish paths and observed values. Values such as field names
    # and expressions are instance data and cannot be treated as finite enums.
    value = (element.text or "").strip()
    schema.observe(path, value if not len(element) and _TOKEN.fullmatch(value) else "")
    for name, value in element.attrib.items():
        schema.observe(f"{path}/@{name}", value if name.lower() not in _INSTANCE_ATTRIBUTES and _TOKEN.fullmatch(value) else "")
    for child in element:
        if isinstance(child.tag, str) and child.tag not in _INSTANCE_TAGS:
            _observe_xml(schema, child, f"{path}/{child.tag}")


def _read_managed_options(schema: ToolConfigSchema, root: Path, inspector: str) -> None:
    axis, assembly, type_name = MANAGED_ENUMS[schema.tool_type]
    path = next(
        (folder / assembly for folder in (root / "bin" / "Plugins", root / "bin") if (folder / assembly).is_file()),
        None,
    )
    if path is None:
        return
    try:
        completed = subprocess.run(
            [inspector, "-t", type_name, str(path)], capture_output=True,
            encoding="utf-8", errors="replace", timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    enum_name = type_name.rsplit("+", 1)[-1]
    declaration = re.search(r"\benum\s+" + re.escape(enum_name) + r"\s*\{([^{}]+)\}", completed.stdout)
    xml_name = axis.rsplit("/", 1)[-1]
    if completed.returncode or declaration is None or f'"{xml_name}"' not in completed.stdout:
        return
    members = [member.partition("=")[0].strip() for member in declaration[1].rstrip().rstrip(",").split(",")]
    if members and all(member.isidentifier() for member in members):
        schema.observe(axis, "", legal_values=members)
        ref = path.relative_to(root).as_posix()
        schema.sources.add(ref)
        schema.engine_bindings[type_name] = {"dll": ref, "sha256": file_hash(path), "xml_axis": axis}


def extract_schemas(alteryx_root: Path, *, tool_type: str | None = None) -> dict[str, ToolConfigSchema]:
    root = alteryx_root.resolve()
    bin_dir = root / "bin"
    if not bin_dir.is_dir():
        raise ValueError(f"Designer installation directory is unavailable: {bin_dir}")
    schemas = {
        kind: ToolConfigSchema(
            kind, category,
            "amp_only" if kind == "ControlContainer" else "classic_and_amp" if kind in AMP_SENSITIVE else "classic_primary",
        )
        for category, kinds in PALETTE_SCOPE.items() for kind in kinds.split()
        if tool_type is None or kind == tool_type
    }
    if not schemas:
        raise ValueError(f"Unknown scope tool: {tool_type}")
    plugins = {entry.plugin_id: entry.tool_type for entry in CATALOG}
    dll_hashes = {}
    for path in sorted((bin_dir / "HtmlPlugins").rglob("*Config.xml")):
        try:
            plugin = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        schema = schemas.get(plugins.get(path.stem.removesuffix("Config"), path.stem.removesuffix("Config").split(".")[-1]))
        if schema is None:
            continue
        schema.sources.add(path.relative_to(root).as_posix())
        for direction in ("Input", "Output"):
            anchors = plugin.findall(f"./GuiSettings/{direction}Connections/Connection")
            if anchors:
                schema.anchors[direction] = [dict(anchor.attrib) for anchor in anchors]
        engine = plugin.find("EngineSettings")
        if engine is not None:
            schema.engine_bindings[path.parent.name] = dict(engine.attrib)
    for entry in CATALOG:
        schema = schemas.get(entry.tool_type)
        if schema is None or not entry.engine_dll:
            continue
        dll = bin_dir / Path(entry.engine_dll).name
        if not dll.is_file():
            dll = bin_dir / "Plugins" / dll.name
        if dll.is_file():
            if dll not in dll_hashes:
                dll_hashes[dll] = file_hash(dll)
            binding = schema.engine_bindings.setdefault(entry.plugin_id, {})
            binding.update(dll=dll.relative_to(root).as_posix(), sha256=dll_hashes[dll], entry_point=entry.engine_entry)

    samples = root / "Samples"
    if (samples / "en").is_dir():
        samples /= "en"
    for folder in (bin_dir / "RuntimeData" / "Macros", samples):
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() not in {".yxmd", ".yxmc", ".yxwz"} or not path.is_file():
                continue
            ref = path.relative_to(root).as_posix()
            try:
                tree = ET.parse(path).getroot()
            except ET.ParseError:
                continue
            if folder != samples:
                macro = schemas.get(_normalize_macro_tool_type(path.name))
                if macro:
                    macro.sources.add(ref)
                    questions = question_manifest(tree)
                    macro.macro_questions[ref] = [asdict(question) for question in questions]
                    action_tree = tree.find("./Properties/RuntimeProperties/Actions")
                    if action_tree is None:
                        action_tree = tree.find("Actions")
                    if action_tree is not None:
                        macro.macro_actions[ref] = [
                            {"kind": action.tag, "id": action.get("id"),
                             "destination": action.get("destination") or action.findtext("Destination")}
                            for action in action_tree.iter() if action.tag.startswith("Action") and action.tag != "Actions"
                        ]
                    for question in questions:
                        macro.observe(f"Questions/{question.name}", str(question.default), legal_values=question.choices)
            for node in tree.iter("Node"):
                gui = node.find("GuiSettings")
                engine = node.find("EngineSettings")
                plugin_id = gui.get("Plugin", "") if gui is not None else ""
                macro_path = engine.get("Macro", "") if engine is not None else ""
                kind = _normalize_tool_type(plugin_id) if plugin_id else _normalize_macro_tool_type(macro_path)
                schema = schemas.get(kind)
                config = node.find("./Properties/Configuration")
                if schema is not None and config is not None:
                    schema.sources.add(ref)
                    _observe_xml(schema, config, "Configuration")
    inspector = shutil.which("ilspycmd")
    for schema in schemas.values():
        if inspector and schema.tool_type in MANAGED_ENUMS:
            _read_managed_options(schema, root, inspector)
        if not schema.sources:
            schema.unresolved.append("No configuration definitions or samples located")
        if any(not axis["declared"] for axis in schema.axes.values()):
            schema.unresolved.append("Some XML paths lack a declared value domain")
        if not schema.axes:
            schema.unresolved.append("Configuration axes have not been enumerated")
    return schemas


def extract_tool_schema(tool_type: str, alteryx_root: Path) -> ToolConfigSchema:
    return extract_schemas(alteryx_root, tool_type=tool_type)[tool_type]


def sync_schemas(alteryx_root: Path, destination: Path, *, tool_type: str | None = None) -> dict:
    schemas = extract_schemas(alteryx_root, tool_type=tool_type)
    destination.mkdir(parents=True, exist_ok=True)
    for kind, schema in schemas.items():
        write_json(destination / f"{kind}.json", schema.to_dict())
    return {"tools": len(schemas), "unresolved_tools": [kind for kind, schema in schemas.items() if schema.unresolved]}
