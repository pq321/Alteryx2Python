"""JSON graph -> .yxmd compiler for the visual workflow editor.

The editor frontend exchanges plain JSON documents (nodes + edges + configs);
this module renders them into official Alteryx .yxmd XML through the same
WorkflowBuilder used by the equivalence test suite, so anything drawn on the
canvas is a real, Designer-loadable workflow.
"""
from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from alteryx2python.workflow_generator import WorkflowBuilder, escape
from alteryx2python.parser.tool_catalog import CATALOG
from alteryx2python.tools.registry import TOOL_REGISTRY

try:
    from .workflow_documents import parse_element, render_document
except ImportError:
    from workflow_documents import parse_element, render_document


def compile_graph_to_yxmd(graph: dict[str, Any]) -> str:
    """Render an editor graph document into .yxmd XML."""
    return render_document(graph, _make_node)


def _make_node(node):
    kind, config = str(node.get("type", "")), node.get("config") or {}
    if "configurationXml" not in config:
        builder = WorkflowBuilder()
        _add_node(builder, node)
        element = ET.fromstring(builder.nodes_xml[-1])
        if kind == "Select":
            for field, settings in zip(element.findall("Properties/Configuration/SelectFields/SelectField"), config.get("fields", [])):
                for key in ("type", "size", "scale", "rename", "description"):
                    if settings.get(key) not in (None, ""):
                        field.set(key, str(settings[key]))
        if kind == "Formula":
            for field, settings in zip(element.findall("Properties/Configuration/FormulaFields/FormulaField"), config.get("expressions", [])):
                if settings.get("scale") not in (None, ""):
                    field.set("scale", str(settings["scale"]))
        return element
    if kind not in TOOL_REGISTRY.list_tool_types() and kind != "Macro" and not kind.startswith("Macro_"):
        raise ValueError(f"unsupported editor tool type: {kind}")
    entry = next((entry for entry in CATALOG if entry.tool_type == kind), None)
    element = ET.Element("Node", ToolID=str(node["id"]))
    gui = ET.SubElement(element, "GuiSettings", Plugin=entry.plugin_id if entry else f"AlteryxBasePluginsGui.{kind}.{kind}")
    ET.SubElement(gui, "Position", x=str(node.get("x", 0)), y=str(node.get("y", 0)))
    properties = ET.SubElement(element, "Properties")
    properties.append(parse_element(config["configurationXml"], "Configuration"))
    if "engineSettingsXml" in config:
        element.append(parse_element(config["engineSettingsXml"], "EngineSettings"))
    else:
        attributes = {}
        if entry:
            attributes = {key: value for key, value in (("EngineDll", entry.engine_dll), ("EngineDllEntryPoint", entry.engine_entry), ("Macro", entry.engine_macro)) if value}
        ET.SubElement(element, "EngineSettings", attributes)
    return element


def _add_node(builder: WorkflowBuilder, node: dict[str, Any]) -> int:
    kind = str(node.get("type", ""))
    config = node.get("config") or {}
    position = (int(node.get("x", 250)), int(node.get("y", 186)))
    if kind == "TextInput":
        fields = [str(field) for field in config.get("fields", [])]
        rows = [list(row) for row in config.get("rows", [])]
        return builder.add_text_input(fields, rows, position)
    if kind == "DbFileInput":
        return builder._node(
            "DbFileInput",
            f'<File FileFormat="0">{escape(config.get("file", ""))}</File>'
            '<FormatSpecificOptions><HeaderRow>True</HeaderRow>'
            '<Delimeter>,</Delimeter><CodePage>65001</CodePage></FormatSpecificOptions>',
            position,
        )
    if kind == "Formula":
        expressions = [
            (str(item.get("field", "")), str(item.get("type", "String")), str(item.get("size", "")), str(item.get("expression", "")))
            for item in config.get("expressions", [])
        ]
        return builder.add_formula(expressions, position)
    if kind == "Filter":
        return builder.add_filter(str(config.get("expression", "")), position)
    if kind == "Select":
        fields = [(str(item.get("field", "")), str(item.get("selected", "True"))) for item in config.get("fields", [])]
        return builder.add_select(fields, include_unknown=bool(config.get("includeUnknown", False)), position=position)
    if kind == "Sort":
        order = [(str(item.get("field", "")), str(item.get("order", "Ascending"))) for item in config.get("order", [])]
        return builder.add_sort(order, position)
    if kind == "Summarize":
        actions = [
            (str(item.get("field", "")), str(item.get("action", "GroupBy")), str(item.get("rename", "")))
            for item in config.get("actions", [])
        ]
        return builder.add_summarize(actions, position)
    if kind == "Join":
        return builder._node(
            "Join", f'<JoinInfo connection="Left"><Field field="{escape(config.get("leftField", ""))}" /></JoinInfo>'
            f'<JoinInfo connection="Right"><Field field="{escape(config.get("rightField", ""))}" /></JoinInfo>',
            position,
        )
    if kind == "Union":
        return builder.add_union(position)
    if kind == "RecordID":
        return builder._node(
            "RecordID", f'<FieldName>{escape(config.get("fieldName", "RecordID"))}</FieldName>'
            '<StartValue>1</StartValue><FieldType>Int64</FieldType><FieldSize>6</FieldSize><Position>0</Position>',
            position,
        )
    if kind == "Sample":
        return builder.add_sample(str(config.get("mode", "First")), str(config.get("n", "10")), position)
    if kind == "Unique":
        return builder.add_unique(str(config.get("field", "")), position)
    if kind == "CrossTab":
        return builder.add_crosstab(
            str(config.get("groupBy", "")),
            str(config.get("header", "")),
            str(config.get("dataField", "")),
            str(config.get("method", "First")),
            position,
        )
    if kind == "Transpose":
        return builder.add_transpose(
            [str(field) for field in config.get("keyFields", [])],
            [str(field) for field in config.get("dataFields", [])],
            position,
        )
    if kind == "RegEx":
        return builder.add_regex(
            str(config.get("field", "")),
            str(config.get("pattern", "")),
            [(str(config.get("outputField", "Parsed")), "V_String", 256)],
            position=position,
        )
    if kind == "DateTime":
        return builder.add_datetime(
            str(config.get("inputField", "")),
            str(config.get("outputField", "")),
            str(config.get("format", "yyyy-MM-dd")).replace("yyyy", "%Y").replace("MM", "%m").replace("dd", "%d"),
            position,
        )
    if kind == "MultiRowFormula":
        return builder.add_multi_row_formula(
            str(config.get("expression", "")), str(config.get("fieldName", "NewField")), position=position
        )
    if kind == "RunningTotal":
        return builder.add_running_total(str(config.get("field", "")), position=position)
    if kind == "Rank":
        return builder.add_rank(str(config.get("field", "")), str(config.get("order", "Descending")), position)
    if kind == "TextToColumns":
        count = int(config.get("numFields", "3"))
        if not 1 <= count <= 100:
            raise ValueError("Text to Columns: column count must be between 1 and 100")
        return builder._node(
            "TextToColumns", f'<Field>{escape(config.get("field", ""))}</Field>'
            f'<Delimeters value="{escape(config.get("delimiter", ","))}" />'
            f'<NumFields value="{count}" /><Flags value="0" /><ErrorHandling>Last</ErrorHandling>'
            f'<RootName>{escape(config.get("rootName") or config.get("field", ""))}</RootName>',
            position,
        )
    if kind == "DbFileOutput":
        tool_id = builder.add_csv_output(str(config.get("file", "output.csv")), position)
        builder.nodes_xml[-1] = builder.nodes_xml[-1].replace('<CodePage>28591</CodePage>', '<CodePage>65001</CodePage>')
        return tool_id
    raise ValueError(f"unsupported editor tool type: {kind}")
