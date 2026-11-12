"""Preserve canonical XML while reconciling Web App graph edits."""
from __future__ import annotations

import base64
from copy import deepcopy
from pathlib import Path, PurePosixPath
import uuid
from xml.etree import ElementTree as ET

from alteryx2python.parser.xml_parser import XmlWorkflowParser

try:
    from .tool_palette import tool_ports
except ImportError:
    from tool_palette import tool_ports

WORKFLOW_SUFFIXES = {".yxmd", ".yxwz", ".yxmc"}


def parse_element(value, tag=None):
    if not isinstance(value, str):
        raise ValueError("XML must be a string")
    if "<!DOCTYPE" in value.upper() or "<!ENTITY" in value.upper():
        raise ValueError("XML entity and document type declarations are not supported")
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    root = ET.fromstring(value, parser=parser)
    if tag and root.tag != tag:
        raise ValueError(f"Expected a complete <{tag}> XML element")
    return root


def xml_text(element, default=""):
    return ET.tostring(element, encoding="unicode") if element is not None else default


def replace_child(parent, child):
    old = parent.find(child.tag)
    if old is None:
        parent.append(child)
    else:
        index = list(parent).index(old)
        parent.remove(old)
        parent.insert(index, child)


def source_path(graph, base_dir):
    if graph.get("sourcePath"):
        return Path(str(graph["sourcePath"])).resolve()
    name = Path(str(graph.get("name") or "workflow.yxmd")).name
    if Path(name).suffix.lower() not in WORKFLOW_SUFFIXES:
        name += ".yxmd"
    return Path(base_dir).resolve() / name


def import_workflow(payload, base_dir):
    name = str(payload.get("name") or "workflow.yxmd")
    if Path(name).suffix.lower() not in WORKFLOW_SUFFIXES:
        raise ValueError("Supported workflows: YXMD, YXWZ, YXMC")
    contents = payload.get("xml")
    if contents is None:
        contents = base64.b64decode(payload.get("content", ""), validate=True).decode("utf-8-sig")
    root = parse_element(contents, "AlteryxDocument")
    path = source_path({**payload, "name": name}, base_dir)
    workflow = XmlWorkflowParser().parse_xml(xml_text(root), path)
    ir_nodes = {node.node_id: node for node in workflow.nodes}
    nodes = []

    def visit(element, parent_id=None):
        node_id = element.get("ToolID", "")
        ir = ir_nodes[node_id]
        position = element.find("GuiSettings/Position")
        engine = element.find("Properties/EngineSettings")
        if engine is None:
            engine = element.find("EngineSettings")
        node = {"id": node_id, "type": ir.tool_type,
                "x": int(position.get("x", 0)) if position is not None else 0,
                "y": int(position.get("y", 0)) if position is not None else 0,
                "config": {"configurationXml": xml_text(element.find("Properties/Configuration"), "<Configuration />"),
                           "engineSettingsXml": xml_text(engine, "<EngineSettings />")},
                "inputs": [anchor.name for anchor in ir.input_anchors],
                "outputs": [anchor.name for anchor in ir.output_anchors]}
        inputs, outputs = tool_ports(ir.tool_type)
        node["inputs"] = list(dict.fromkeys([*node["inputs"], *inputs]))
        node["outputs"] = list(dict.fromkeys([*node["outputs"], *outputs]))
        if parent_id is not None:
            node["parentId"] = parent_id
        nodes.append(node)
        for child in element.findall("ChildNodes/Node"):
            visit(child, node_id)

    for element in root.findall("Nodes/Node"):
        visit(element)
    return {"name": name, "workflowXml": xml_text(root), "sourcePath": path.as_posix(), "nodes": nodes,
            "edges": [{"from": e.source_node_id, "fromAnchor": e.source_anchor,
                       "to": e.target_node_id, "toAnchor": e.target_anchor} for e in workflow.edges]}


def apply_workflow_settings(root, graph):
    if "propertiesXml" in graph:
        replace_child(root, parse_element(graph["propertiesXml"], "Properties"))
    properties = root.find("Properties")
    for key, tag in (("runtimePropertiesXml", "RuntimeProperties"), ("eventsXml", "Events"), ("constantsXml", "Constants")):
        if key in graph:
            if properties is None:
                properties = ET.SubElement(root, "Properties")
            replace_child(properties, parse_element(graph[key], tag))
    return root


def render_document(graph, make_node):
    root = parse_element(graph["workflowXml"], "AlteryxDocument") if graph.get("workflowXml") else ET.Element("AlteryxDocument", yxmdVer="2024.1")
    original = {e.get("ToolID"): e for e in root.iter("Node")}
    if len(original) != sum(1 for _ in root.iter("Node")):
        raise ValueError("Source XML contains duplicate ToolIDs")
    old_nodes = root.find("Nodes")
    new_nodes = deepcopy(old_nodes) if old_nodes is not None else ET.Element("Nodes")
    for element in list(new_nodes):
        if element.tag == "Node":
            new_nodes.remove(element)
    rendered, parents = {}, {}
    for node in graph.get("nodes", []):
        node_id = str(node["id"])
        if not node_id or node_id in rendered:
            raise ValueError(f"Invalid or duplicate node: {node_id}")
        element = deepcopy(original[node_id]) if node_id in original else make_node(node)
        element.set("ToolID", node_id)
        children = element.find("ChildNodes")
        if children is not None:
            for child in list(children):
                if child.tag == "Node":
                    children.remove(child)
        config = node.get("config") or {}
        properties = element.find("Properties")
        if "configurationXml" in config:
            configuration = parse_element(config["configurationXml"], "Configuration")
            existing = properties.find("Configuration") if properties is not None else None
            if existing is not None or configuration.attrib or list(configuration) or configuration.text or node_id not in original:
                if properties is None:
                    properties = ET.SubElement(element, "Properties")
                replace_child(properties, configuration)
        elif node_id in original:
            if properties is None:
                properties = ET.SubElement(element, "Properties")
            replace_child(properties, make_node(node).find("Properties/Configuration"))
        if "engineSettingsXml" in config:
            engine = parse_element(config["engineSettingsXml"], "EngineSettings")
            owner = properties if properties is not None and properties.find("EngineSettings") is not None else element
            if owner.find("EngineSettings") is not None or engine.attrib or list(engine) or engine.text or node_id not in original:
                replace_child(owner, engine)
        gui = element.find("GuiSettings")
        moved = any(int(node.get(key, 0)) for key in ("x", "y"))
        if gui is None and moved:
            gui = ET.SubElement(element, "GuiSettings")
        position = gui.find("Position") if gui is not None else None
        if position is None and moved:
            position = ET.SubElement(gui, "Position")
        for key in ("x", "y"):
            if key in node and position is not None:
                position.set(key, str(int(node[key])))
        rendered[node_id] = element
        parents[node_id] = str(node["parentId"]) if node.get("parentId") is not None else None
    for node_id, element in rendered.items():
        parent_id, visited = parents[node_id], {node_id}
        while parent_id is not None:
            if parent_id not in rendered or parent_id in visited:
                raise ValueError(f"Missing or cyclic container parent for node {node_id}")
            visited.add(parent_id)
            parent_id = parents[parent_id]
        parent_id = parents[node_id]
        if parent_id is None:
            new_nodes.append(element)
        else:
            children = rendered[parent_id].find("ChildNodes")
            if children is None:
                children = ET.SubElement(rendered[parent_id], "ChildNodes")
            children.append(element)
    replace_child(root, new_nodes)
    existing = root.find("Connections")
    connections = deepcopy(existing) if existing is not None else ET.Element("Connections")
    old_edges = {}
    for connection in list(connections):
        if connection.tag != "Connection":
            continue
        origin, destination = connection.find("Origin"), connection.find("Destination")
        if origin is not None and destination is not None:
            key = (origin.get("ToolID"), origin.get("Connection"), destination.get("ToolID"), destination.get("Connection"))
            old_edges[key] = connection
        connections.remove(connection)
    seen = set()
    for edge in graph.get("edges", []):
        key = (str(edge["from"]), str(edge.get("fromAnchor", "Output")), str(edge["to"]), str(edge.get("toAnchor", "Input")))
        if key[0] not in rendered or key[2] not in rendered:
            raise ValueError("Connection references an unknown node")
        if key in seen:
            raise ValueError("Duplicate connection")
        seen.add(key)
        connection = deepcopy(old_edges[key]) if key in old_edges else ET.Element("Connection")
        if key not in old_edges:
            ET.SubElement(connection, "Origin", ToolID=key[0], Connection=key[1])
            ET.SubElement(connection, "Destination", ToolID=key[2], Connection=key[3])
        connections.append(connection)
    replace_child(root, connections)
    apply_workflow_settings(root, graph)
    return xml_text(root)


def import_macro(payload, uploads):
    name = str(payload.get("name") or "macro.yxmc")
    files = [{"name": name, "xml": payload.get("xml"), "content": payload.get("content", "")}, *payload.get("files", [])]
    prepared = {}
    for item in files:
        relative = PurePosixPath(str(item["name"]).replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts or ":" in str(relative) or relative.suffix.lower() != ".yxmc":
            raise ValueError("Macro names must be relative .yxmc paths without traversal")
        if relative.as_posix().casefold() in {p.casefold() for p in prepared}:
            raise ValueError("Duplicate macro path")
        contents = item.get("xml")
        if contents is None:
            contents = base64.b64decode(item.get("content", ""), validate=True).decode("utf-8-sig")
        prepared[relative.as_posix()] = xml_text(parse_element(contents, "AlteryxDocument"))
    bundle = Path(uploads).resolve() / "macros" / uuid.uuid4().hex
    for relative, contents in prepared.items():
        XmlWorkflowParser().parse_xml(contents, bundle / relative)
    main_name = PurePosixPath(name.replace("\\", "/")).as_posix()
    graph = import_workflow({"name": name, "xml": prepared[main_name], "sourcePath": str(bundle / main_name)}, bundle)
    for relative, contents in prepared.items():
        destination = bundle / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(contents, encoding="utf-8")
    inputs, outputs = [], []
    types = {n["id"]: n["type"] for n in graph["nodes"]}
    for element in parse_element(graph["workflowXml"]).iter("Node"):
        kind = types.get(element.get("ToolID"))
        if kind in {"MacroInput", "MacroOutput"}:
            (inputs if kind == "MacroInput" else outputs).append(element.findtext("Properties/Configuration/Name") or ("Input" if kind == "MacroInput" else "Output"))
    tool = {"type": "Macro_" + Path(name).stem, "label": Path(name).stem, "category": "Macros", "inputs": inputs, "outputs": outputs,
            "multiInput": True, "advancedConfig": True, "executionProfile": "local-static-macro",
            "defaults": {"configurationXml": "<Configuration />", "engineSettingsXml": xml_text(ET.Element("EngineSettings", Macro=graph["sourcePath"]))}}
    return {"name": name, "path": graph["sourcePath"], "tool": tool, "graph": graph,
            "files": [{"name": p, "path": (bundle / p).as_posix()} for p in prepared]}
