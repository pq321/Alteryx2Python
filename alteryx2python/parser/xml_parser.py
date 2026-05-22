from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree

from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR, WorkflowIR
from alteryx2python.parser.base_parser import BaseWorkflowParser
from alteryx2python.parser.tool_parsers import (
    parse_dbfileinput_config,
    parse_filter_config,
    parse_formula_config,
    parse_join_config,
    parse_jsonparse_config,
    parse_recordid_config,
    parse_select_config,
    parse_transpose_config,
    parse_union_config,
)


INPUT_ANCHOR_HINTS = {
    "Action",
    "Input",
    "Input2",
    "Join",
    "Left",
    "Question",
    "Right",
    "Targets",
}

INTERFACE_PLUGIN_PREFIX = "AlteryxGuiToolkit.Questions."
ACTION_PLUGIN = "AlteryxGuiToolkit.Action.Action"
CONTAINER_PLUGIN = "AlteryxGuiToolkit.ToolContainer.ToolContainer"


def _normalize_tool_type(plugin_name: str) -> str:
    if plugin_name == CONTAINER_PLUGIN:
        return "ToolContainer"
    if plugin_name == ACTION_PLUGIN:
        return "Action"
    if plugin_name.startswith(INTERFACE_PLUGIN_PREFIX):
        suffix = plugin_name.removeprefix(INTERFACE_PLUGIN_PREFIX)
        if suffix == "FileBrowse.FileBrowse":
            return "QuestionFileBrowse"
        if suffix == "TextBox.QuestionTextBox":
            return "QuestionTextBox"
        if suffix == "Tab.Tab":
            return "QuestionTab"
        return suffix.split(".")[-1]
    if plugin_name.startswith("AlteryxBasePluginsGui."):
        tail = plugin_name.split(".")[-1]
        if tail == "AlteryxSelect":
            return "Select"
        if tail == "JSONParse":
            return "JSONParse"
        if tail == "DbFileInput":
            return "DbFileInput"
        if tail == "DbFileOutput":
            return "DbFileOutput"
        return tail
    if plugin_name.startswith("AlteryxConnectorGui."):
        return plugin_name.split(".")[-1]
    return plugin_name.split(".")[-1] if plugin_name else "UNKNOWN"


def _node_supported_status(plugin_name: str) -> tuple[str, str | None]:
    if plugin_name == CONTAINER_PLUGIN:
        return "L1_CONTAINER_ONLY", None
    if plugin_name == ACTION_PLUGIN:
        return "L0_DEFERRED_ACTION_NODE", "Deferred action node requires interface/update semantics"
    if plugin_name.startswith(INTERFACE_PLUGIN_PREFIX):
        return "L0_DEFERRED_INTERFACE_NODE", "Deferred interface node requires app/question semantics"
    if plugin_name.startswith("AlteryxConnectorGui."):
        return "L0_DEFERRED_CONNECTOR_NODE", "Deferred connector node requires external service semantics"
    return "L1_PARSED_ONLY", None


def _element_to_dict(element: ElementTree.Element) -> dict[str, object]:
    data: dict[str, object] = {}
    if element.attrib:
        data["attributes"] = dict(element.attrib)
    text = (element.text or "").strip()
    if text:
        data["text"] = text
    children = list(element)
    if children:
        grouped: dict[str, list[dict[str, object]]] = {}
        for child in children:
            grouped.setdefault(child.tag, []).append(_element_to_dict(child))
        for tag, entries in grouped.items():
            data[tag] = entries if len(entries) > 1 else entries[0]
    return data


TOOL_PARSERS = {
    "DbFileInput": parse_dbfileinput_config,
    "Filter": parse_filter_config,
    "Formula": parse_formula_config,
    "Join": parse_join_config,
    "JSONParse": parse_jsonparse_config,
    "RecordID": parse_recordid_config,
    "Select": parse_select_config,
    "Transpose": parse_transpose_config,
    "Union": parse_union_config,
}


def _field_schema(field: ElementTree.Element) -> dict[str, str]:
    return dict(field.attrib)


def _record_info_to_schema(meta_info: ElementTree.Element | None) -> dict[str, object]:
    if meta_info is None:
        return {}
    record_info = meta_info.find("RecordInfo")
    if record_info is None:
        return {"connection": meta_info.attrib.get("connection", "")}
    return {
        "connection": meta_info.attrib.get("connection", ""),
        "fields": [_field_schema(field) for field in record_info.findall("Field")],
    }


def _extract_external_dependencies(node_element: ElementTree.Element) -> list[str]:
    dependencies: list[str] = []
    for file_element in node_element.findall(".//File"):
        text = (file_element.text or "").strip()
        if text:
            dependencies.append(text)
    return dependencies


def _extract_node_anchors(
    node_element: ElementTree.Element,
    incoming_anchor_names: set[str],
    outgoing_anchor_names: set[str],
) -> tuple[list[AnchorIR], list[AnchorIR]]:
    input_anchors = [AnchorIR(name=name, direction="input") for name in sorted(incoming_anchor_names)]
    output_anchors = [AnchorIR(name=name, direction="output") for name in sorted(outgoing_anchor_names)]

    meta_infos = node_element.findall("./Properties/MetaInfo")
    input_names = {anchor.name for anchor in input_anchors}
    output_names = {anchor.name for anchor in output_anchors}
    for meta_info in meta_infos:
        connection_name = meta_info.attrib.get("connection", "").strip()
        if not connection_name:
            continue
        if connection_name in incoming_anchor_names or connection_name in INPUT_ANCHOR_HINTS:
            if connection_name not in input_names:
                input_anchors.append(AnchorIR(name=connection_name, direction="input"))
                input_names.add(connection_name)
        else:
            if connection_name not in output_names:
                output_anchors.append(AnchorIR(name=connection_name, direction="output"))
                output_names.add(connection_name)
    return input_anchors, output_anchors


def _find_root_nodes(root: ElementTree.Element) -> list[ElementTree.Element]:
    return root.findall("./Nodes/Node")


def _build_edges(root: ElementTree.Element) -> list[EdgeIR]:
    edges: list[EdgeIR] = []
    for connection in root.findall("./Connections/Connection"):
        origin = connection.find("Origin")
        destination = connection.find("Destination")
        if origin is None or destination is None:
            continue
        source_node_id = origin.attrib.get("ToolID", "")
        source_anchor = origin.attrib.get("Connection", "")
        target_node_id = destination.attrib.get("ToolID", "")
        target_anchor = destination.attrib.get("Connection", "")
        edge_id = f"{source_node_id}:{source_anchor}->{target_node_id}:{target_anchor}"
        edges.append(
            EdgeIR(
                edge_id=edge_id,
                source_node_id=source_node_id,
                source_anchor=source_anchor,
                target_node_id=target_node_id,
                target_anchor=target_anchor,
                metadata={"raw": _element_to_dict(connection)},
            )
        )
    return edges


def _iter_nodes(node_element: ElementTree.Element, container_id: str | None = None):
    yield node_element, container_id
    child_nodes = node_element.find("ChildNodes")
    if child_nodes is not None:
        parent_tool_id = node_element.attrib.get("ToolID")
        for child_node in child_nodes.findall("Node"):
            yield from _iter_nodes(child_node, container_id=parent_tool_id)


class XmlWorkflowParser(BaseWorkflowParser):
    """Parses Alteryx XML workflows into the canonical IR shell."""

    def parse(self, source_path: Path) -> WorkflowIR:
        contents = source_path.read_bytes()
        root = ElementTree.fromstring(contents)
        edges = _build_edges(root)

        incoming_anchor_names: dict[str, set[str]] = defaultdict(set)
        outgoing_anchor_names: dict[str, set[str]] = defaultdict(set)
        incoming_edge_ids: dict[str, list[str]] = defaultdict(list)
        outgoing_edge_ids: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            incoming_anchor_names[edge.target_node_id].add(edge.target_anchor)
            outgoing_anchor_names[edge.source_node_id].add(edge.source_anchor)
            incoming_edge_ids[edge.target_node_id].append(edge.edge_id)
            outgoing_edge_ids[edge.source_node_id].append(edge.edge_id)

        nodes: list[NodeIR] = []
        warnings: list[str] = []
        external_dependencies: set[str] = set()

        for root_node in _find_root_nodes(root):
            for node_element, container_id in _iter_nodes(root_node):
                node_id = node_element.attrib.get("ToolID", "")
                gui_settings = node_element.find("GuiSettings")
                plugin_name = gui_settings.attrib.get("Plugin", "UNKNOWN") if gui_settings is not None else "UNKNOWN"
                tool_type = _normalize_tool_type(plugin_name)
                supported_status, warning = _node_supported_status(plugin_name)
                if warning:
                    warnings.append(f"Node {node_id} ({tool_type}): {warning}")

                configuration = node_element.find("./Properties/Configuration")
                raw_config = _element_to_dict(configuration) if configuration is not None else {}
                if container_id is not None:
                    raw_config["container_id"] = container_id

                child_nodes = node_element.find("ChildNodes")
                if child_nodes is not None:
                    raw_config["child_node_ids"] = [child.attrib.get("ToolID", "") for child in child_nodes.findall("Node")]

                meta_infos = node_element.findall("./Properties/MetaInfo")
                schema_by_connection = {
                    meta_info.attrib.get("connection", ""): _record_info_to_schema(meta_info)
                    for meta_info in meta_infos
                    if meta_info.attrib.get("connection", "")
                }
                if len(schema_by_connection) == 1:
                    expected_output_schema = dict(next(iter(schema_by_connection.values())))
                else:
                    expected_output_schema = schema_by_connection

                metadata: dict[str, object] = {
                    "plugin_name": plugin_name,
                    "raw_gui_settings": _element_to_dict(gui_settings) if gui_settings is not None else {},
                    "meta_info": schema_by_connection,
                }
                annotation = node_element.find("./Properties/Annotation")
                if annotation is not None:
                    metadata["annotation"] = _element_to_dict(annotation)

                input_anchors, output_anchors = _extract_node_anchors(
                    node_element,
                    incoming_anchor_names.get(node_id, set()),
                    outgoing_anchor_names.get(node_id, set()),
                )

                parser = TOOL_PARSERS.get(tool_type)
                if parser is None:
                    normalized_config = raw_config
                else:
                    parsed = parser(raw_config)
                    normalized_config = parsed.normalized_config
                    warnings.extend(
                        [f"Node {node_id} ({tool_type}): {message}" for message in parsed.warnings]
                    )

                for dependency in _extract_external_dependencies(node_element):
                    external_dependencies.add(dependency)

                config = {
                    **raw_config,
                    "raw": raw_config,
                    "normalized": normalized_config,
                }

                nodes.append(
                    NodeIR(
                        node_id=node_id,
                        source_tool_id=node_id,
                        tool_type=tool_type,
                        tool_name=plugin_name,
                        config=config,
                        input_anchors=input_anchors,
                        output_anchors=output_anchors,
                        incoming_edges=list(incoming_edge_ids.get(node_id, [])),
                        outgoing_edges=list(outgoing_edge_ids.get(node_id, [])),
                        expected_input_schema={},
                        expected_output_schema=expected_output_schema,
                        metadata=metadata,
                        supported_status=supported_status,
                    )
                )

        return WorkflowIR(
            workflow_id=root.attrib.get("WorkflowId", source_path.stem),
            workflow_name=root.attrib.get("name", source_path.stem),
            source_file=str(source_path),
            source_hash=sha256(contents).hexdigest(),
            parser_version="0.1.0",
            migration_spec_version="0.1.0",
            nodes=nodes,
            edges=edges,
            external_dependencies=sorted(external_dependencies),
            warnings=warnings,
            classification="CLASS_D_PARTIAL_MIGRATION_ONLY",
        )
