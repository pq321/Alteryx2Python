"""Catalog-backed graph construction and structural XML preservation.

JSON nodes accept tool_type/plugin_id, configuration_xml, macro_path, template_xml
and explicit ports. Templates retain unknown GUI/engine/configuration properties.
Constructibility is separate from executable/native-certified behavior.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from alteryx2python.parser.tool_catalog import CATALOG, catalog_entry_for_plugin
from alteryx2python.tools.registry import TOOL_REGISTRY


@dataclass
class NodeSpec:
    node_id: str
    tool_type: str
    configuration_xml: str | None = None
    plugin_id: str | None = None
    engine_dll: str | None = None
    engine_entry: str | None = None
    position: tuple[int, int] = (100, 100)
    macro_path: str | None = None
    input_anchors: tuple[str, ...] | None = None
    output_anchors: tuple[str, ...] | None = None
    template_xml: str | None = None
    source_dir: str | None = None

    def binding(self):
        entry = catalog_entry_for_plugin(self.plugin_id or self.tool_type)
        if entry is None:
            entry = next((e for e in CATALOG if e.tool_type == self.tool_type), None)
        if not entry and not self.template_xml and not self.macro_path:
            if not self.plugin_id or not (self.engine_dll and self.engine_entry):
                raise ValueError(
                    f"Unknown tool {self.tool_type}: provide a node template or explicit plugin/engine binding"
                )
        return entry

    def ports(self, direction):
        explicit = getattr(self, direction + "_anchors")
        if explicit is not None:
            return set(explicit)
        if self.template_xml:
            return (
                None  # Port inventories are not generally encoded in native node XML.
            )
        metadata = TOOL_REGISTRY._registry.get(self.tool_type)
        if metadata and metadata.execution_profile != "unavailable":
            return set(getattr(metadata, direction + "_anchors"))
        return None

    def element(self):
        entry = self.binding()
        node = (
            ET.fromstring(self.template_xml)
            if self.template_xml
            else ET.Element("Node")
        )
        if node.tag != "Node":
            raise ValueError("template_xml must contain a single Node element")
        node.set("ToolID", str(self.node_id))
        gui = _child(node, "GuiSettings")
        plugin = self.plugin_id or (entry.plugin_id if entry else "")
        if self.plugin_id is not None or not self.template_xml:
            gui.set("Plugin", plugin)
        if not self.template_xml:
            ET.SubElement(
                gui,
                "Position",
                {"x": str(self.position[0]), "y": str(self.position[1])},
            )
        props = _child(node, "Properties")
        if self.configuration_xml is not None:
            current = props.find("Configuration")
            if current is not None:
                props.remove(current)
            wrapped = ET.fromstring(
                "<Configuration>" + self.configuration_xml + "</Configuration>"
            )
            if len(wrapped) == 1 and wrapped[0].tag == "Configuration":
                wrapped = deepcopy(wrapped[0])
            props.insert(0, wrapped)
        elif props.find("Configuration") is None:
            ET.SubElement(props, "Configuration")
        engine = _child(node, "EngineSettings")
        macro = self.macro_path or (
            entry.engine_macro if entry and not self.template_xml else None
        )
        dll = self.engine_dll or (
            entry.engine_dll if entry and not self.template_xml else None
        )
        function = self.engine_entry or (
            entry.engine_entry if entry and not self.template_xml else None
        )
        if macro:
            engine.set("Macro", macro)
        elif dll and function:
            engine.set("EngineDll", dll)
            engine.set("EngineDllEntryPoint", function)
        elif not self.template_xml and not (entry and entry.gui_only):
            raise ValueError(
                f"Native engine binding is unknown for {self.tool_type}; import its installed node template"
            )
        if self.source_dir:
            from alteryx2python.parser.file_references import resolve_file_references

            resolve_file_references(node, Path(self.source_dir) / "source.yxmd")
        return node


@dataclass
class EdgeSpec:
    source: str
    target: str
    source_anchor: str = "Output"
    target_anchor: str = "Input"
    control: bool = False
    template_xml: str | None = None


def _child(parent, tag):
    found = parent.find(tag)
    return found if found is not None else ET.SubElement(parent, tag)


@dataclass
class WorkflowSpec:
    nodes: list[NodeSpec] = field(default_factory=list)
    edges: list[EdgeSpec] = field(default_factory=list)
    kind: str = "yxmd"
    source_xml: str | None = None
    properties_xml: str | None = None
    base_dir: str | None = None

    @classmethod
    def from_json(cls, value):
        data = json.loads(value) if isinstance(value, str) else value
        nodes = [
            NodeSpec(**{**n, "node_id": str(n["node_id"])})
            for n in data.get("nodes", [])
        ]
        edges = [
            EdgeSpec(**{**e, "source": str(e["source"]), "target": str(e["target"])})
            for e in data.get("edges", [])
        ]
        result = cls(
            nodes,
            edges,
            data.get("kind", "yxmd"),
            data.get("source_xml"),
            data.get("properties_xml"),
            data.get("base_dir"),
        )
        result.validate()
        return result

    def to_json(self):
        self.validate()
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    def validate(self):
        if self.kind not in {"yxmd", "yxmc", "yxwz"}:
            raise ValueError("kind must be yxmd, yxmc or yxwz")
        by_id = {}
        for node in self.nodes:
            if not str(node.node_id).isdigit() or int(node.node_id) < 1:
                raise ValueError("native ToolID must be a positive integer")
            element = node.element()
            for child in element.iter("Node"):
                key = child.get("ToolID")
                if key in by_id:
                    raise ValueError(f"duplicate node ID: {key}")
                by_id[key] = node if key == node.node_id else None
        graph = {key: [] for key in by_id}
        seen = set()
        for edge in self.edges:
            if edge.source not in by_id or edge.target not in by_id:
                raise ValueError("edge references unknown node")
            identity = (
                edge.source,
                edge.source_anchor,
                edge.target,
                edge.target_anchor,
            )
            if identity in seen:
                raise ValueError("duplicate connection")
            seen.add(identity)
            if edge.control:
                if edge.source_anchor not in {
                    "Question",
                    "Q",
                    "Action",
                    "True",
                    "False",
                    "Condition",
                } or edge.target_anchor not in {"Question", "Q", "Action", "Condition"}:
                    raise ValueError(
                        "control connections require interface/control anchors"
                    )
                source = by_id[edge.source]
                ports = source.ports("output") if source else None
                if ports is not None and edge.source_anchor not in ports:
                    raise ValueError("Source tool has no declared control output")
                continue
            graph[edge.source].append(edge.target)
            for key, direction, anchor in (
                (edge.source, "output", edge.source_anchor),
                (edge.target, "input", edge.target_anchor),
            ):
                node = by_id[key]
                ports = node.ports(direction) if node else None
                if ports is None and node and not node.template_xml:
                    raise ValueError(
                        f"Declare {direction}_anchors for {node.tool_type}"
                    )
                if ports is not None and anchor not in ports:
                    raise ValueError(f"unknown {direction} anchor {anchor} on {key}")
        visiting, done = set(), set()

        def visit(key):
            if key in visiting:
                raise ValueError("data graph contains a cycle")
            if key in done:
                return
            visiting.add(key)
            for target in graph[key]:
                visit(target)
            visiting.remove(key)
            done.add(key)

        for key in graph:
            visit(key)

    def to_xml(self):
        self.validate()
        root = (
            ET.fromstring(self.source_xml)
            if self.source_xml
            else ET.Element("AlteryxDocument", {"yxmdVer": "2025.1"})
        )
        nodes = _child(root, "Nodes")
        for child in list(nodes):
            if child.tag == "Node":
                nodes.remove(child)
        nodes.extend(node.element() for node in self.nodes)
        connections = _child(root, "Connections")
        for child in list(connections):
            if child.tag == "Connection":
                connections.remove(child)
        for edge in self.edges:
            connection = (
                ET.fromstring(edge.template_xml)
                if edge.template_xml
                else ET.Element("Connection")
            )
            _child(connection, "Origin").attrib.update(
                ToolID=edge.source, Connection=edge.source_anchor
            )
            _child(connection, "Destination").attrib.update(
                ToolID=edge.target, Connection=edge.target_anchor
            )
            connections.append(connection)
        props = _child(root, "Properties")
        if self.properties_xml is not None:
            replacement = ET.fromstring(self.properties_xml)
            if replacement.tag != "Properties":
                raise ValueError("properties_xml must contain a Properties element")
            root.remove(props)
            root.append(replacement)
            props = replacement
        if not self.source_xml and self.properties_xml is None:
            runtime = _child(props, "RuntimeProperties")
            _child(runtime, "ModuleType").text = {
                "yxmc": "Macro",
                "yxwz": "Wizard",
                "yxmd": "Standard",
            }[self.kind]
        if self.base_dir:
            from alteryx2python.parser.file_references import resolve_file_references

            resolve_file_references(root, Path(self.base_dir) / "source.yxmd")
        return ET.tostring(root, encoding="unicode")


def load_workflow_spec(path):
    path = Path(path)
    if path.suffix.lower() == ".json":
        spec = WorkflowSpec.from_json(path.read_text(encoding="utf-8-sig"))
        spec.base_dir = spec.base_dir or str(path.resolve().parent)
        return spec
    root = ET.parse(path).getroot()
    nodes = []
    for element in root.findall("./Nodes/Node"):
        gui = element.find("GuiSettings")
        plugin = gui.get("Plugin", "") if gui is not None else ""
        entry = catalog_entry_for_plugin(plugin)
        nodes.append(
            NodeSpec(
                element.get("ToolID"),
                entry.tool_type if entry else plugin,
                template_xml=ET.tostring(element, encoding="unicode"),
            )
        )
    edges = []
    for element in root.findall("./Connections/Connection"):
        origin, destination = element.find("Origin"), element.find("Destination")
        if origin is None or destination is None:
            raise ValueError("connection requires Origin and Destination")
        out, inp = origin.get("Connection", ""), destination.get("Connection", "")
        control = inp in {"Question", "Q", "Action", "Condition"}
        edges.append(
            EdgeSpec(
                origin.get("ToolID"),
                destination.get("ToolID"),
                out,
                inp,
                control,
                ET.tostring(element, encoding="unicode"),
            )
        )
    result = WorkflowSpec(
        nodes,
        edges,
        path.suffix.lower().lstrip("."),
        ET.tostring(root, encoding="unicode"),
        base_dir=str(path.resolve().parent),
    )
    result.validate()
    return result
