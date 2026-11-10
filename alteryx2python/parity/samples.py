"""Small, authored local examples; no copied vendor implementation or data."""

from pathlib import Path
from xml.etree import ElementTree as ET


def generate_samples(destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, expression, null_case in (
        ("branch_duplicates_unicode", '[key] = "a"', False),
        ("empty_branch", '[key] = "absent"', False),
        ("null_empty_unicode", '[key] = "a"', True),
        ("missing_field_error", "[missing_field] > 0", False),
    ):
        root = ET.Element("AlteryxDocument", yxmdVer="2025.1")
        nodes = ET.SubElement(root, "Nodes")
        text = _node(nodes, 1, "TextInput", "AlteryxTextInput")
        fields = ET.SubElement(text, "Fields")
        for field in ("key", "label"):
            ET.SubElement(fields, "Field", name=field)
        data = ET.SubElement(text, "Data")
        rows = [("a", "中文"), ("b", ""), ("a", "中文"), ("c", "é🙂")]
        if null_case:
            rows.append(("a", None))
        for values in rows:
            row = ET.SubElement(data, "r")
            for value in values:
                cell = ET.SubElement(row, "c")
                if value is not None:
                    cell.text = value
                    # Designer serializes an empty cell as <c/>; native value is null.
        ET.SubElement(text, "NumRows", value=str(len(rows)))
        filter_config = _node(nodes, 2, "Filter", "AlteryxFilter")
        ET.SubElement(filter_config, "Mode").text = "Custom"
        ET.SubElement(filter_config, "Expression").text = expression
        unique = _node(nodes, 3, "Unique", "AlteryxUnique")
        ET.SubElement(ET.SubElement(unique, "UniqueFields"), "Field", field="key")
        connections = ET.SubElement(root, "Connections")
        _edge(connections, 1, "Output", 2, "Input")
        _edge(connections, 2, "True", 3, "Input")
        properties = ET.SubElement(root, "Properties")
        runtime = ET.SubElement(properties, "RuntimeProperties")
        ET.SubElement(runtime, "EnableEngine2", value="False")
        ET.SubElement(runtime, "DisableAllOutput", value="False")
        ET.SubElement(
            root, "EngineSettings", EngineDll="", EngineDllEntryPoint="", Macro=""
        )
        path = destination / f"{name}.yxmd"
        if path.exists():
            raise FileExistsError(path)
        ET.indent(root)
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        paths.append(path)
    # Many-to-many join, including all three output anchors.
    root = ET.parse(paths[0]).getroot()
    nodes = root.find("Nodes")
    nodes.remove(nodes.find("Node[@ToolID='2']"))
    nodes.remove(nodes.find("Node[@ToolID='3']"))
    right = ET.fromstring(ET.tostring(nodes.find("Node[@ToolID='1']")))
    right.set("ToolID", "2")
    nodes.append(right)
    join = _node(nodes, 3, "Join", "AlteryxJoin")
    join.set("joinByRecordPos", "False")
    for connection in ("Left", "Right"):
        ET.SubElement(
            ET.SubElement(join, "JoinInfo", connection=connection), "Field", field="key"
        )
    select = ET.SubElement(
        ET.SubElement(join, "SelectConfiguration"),
        "Configuration",
        outputConnection="Join",
    )
    selected = ET.SubElement(select, "SelectFields")
    for prefix in ("Left_", "Right_"):
        for field in ("key", "label"):
            ET.SubElement(
                selected,
                "SelectField",
                field=prefix + field,
                selected="True",
                rename=prefix + field,
                input=prefix,
            )
    root.remove(root.find("Connections"))
    connections = ET.SubElement(root, "Connections")
    _edge(connections, 1, "Output", 3, "Left")
    _edge(connections, 2, "Output", 3, "Right")
    path = destination / "join_multiplicity.yxmd"
    if path.exists():
        raise FileExistsError(path)
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    paths.append(path)
    # Native XML empty cells are null; a Formula supplies an actual empty string.
    root = ET.parse(paths[0]).getroot()
    nodes = root.find("Nodes")
    nodes.remove(nodes.find("Node[@ToolID='2']"))
    nodes.remove(nodes.find("Node[@ToolID='3']"))
    config = _node(nodes, 2, "Formula", "AlteryxFormula")
    ET.SubElement(
        ET.SubElement(config, "FormulaFields"),
        "FormulaField",
        expression='""',
        field="empty_text",
        type="V_WString",
        size="16",
    )
    root.remove(root.find("Connections"))
    connections = ET.SubElement(root, "Connections")
    _edge(connections, 1, "Output", 2, "Input")
    path = destination / "null_vs_empty_formula.yxmd"
    if path.exists():
        raise FileExistsError(path)
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    paths.append(path)
    return paths


def _node(nodes: ET.Element, node_id: int, name: str, entry: str) -> ET.Element:
    node = ET.SubElement(nodes, "Node", ToolID=str(node_id))
    gui = ET.SubElement(
        node, "GuiSettings", Plugin=f"AlteryxBasePluginsGui.{name}.{name}"
    )
    ET.SubElement(gui, "Position", x=str(node_id * 150), y="100")
    config = ET.SubElement(ET.SubElement(node, "Properties"), "Configuration")
    ET.SubElement(
        node,
        "EngineSettings",
        EngineDll="AlteryxBasePluginsEngine.dll",
        EngineDllEntryPoint=entry,
    )
    return config


def _edge(
    connections: ET.Element, source: int, output: str, target: int, anchor: str
) -> None:
    edge = ET.SubElement(connections, "Connection")
    ET.SubElement(edge, "Origin", ToolID=str(source), Connection=output)
    ET.SubElement(edge, "Destination", ToolID=str(target), Connection=anchor)
