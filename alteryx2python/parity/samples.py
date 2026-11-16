"""Small, authored local examples; no copied vendor implementation or data."""

from pathlib import Path
from xml.etree import ElementTree as ET

from alteryx2python.workflow_generator import WorkflowBuilder


def generate_control_log_sample(destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=False)
    builder = WorkflowBuilder()
    source = builder.add_text_input(["x"], [["1"]], position=(120, 170))
    container_plugin = "AlteryxGuiToolkit.ControlContainer.ControlContainer"
    first = builder._node("ControlContainer", '<Caption>First</Caption><Disabled value="False"/>',
                          (240, 90), gui_plugin=container_plugin)
    second = builder._node("ControlContainer", '<Caption>Second</Caption><Disabled value="False"/>',
                           (520, 90), gui_plugin=container_plugin)
    warning = builder._node(
        "Message",
        '<When>First</When><Type>Warning</Type><Priority>Normal</Priority><Transient>False</Transient>'
        '<MessageExpression>"warning in first container"</MessageExpression>',
        (270, 150),
    )
    deferred = builder._node(
        "Message",
        '<When>All</When><Type>Message</Type><Priority>Normal</Priority><Transient>False</Transient>'
        '<MessageExpression>"last message in first container"</MessageExpression>',
        (385, 150),
    )
    after = builder._node(
        "Message",
        '<When>First</When><Type>Message</Type><Priority>Normal</Priority><Transient>False</Transient>'
        '<MessageExpression>"message in second container"</MessageExpression>',
        (550, 150),
    )
    browse = builder._node("BrowseV2", "", (740, 150))
    builder.connect(source, warning)
    builder.connect(warning, deferred)
    builder.connect(source, after)
    builder.connect(first, second, "Log", "Control")
    builder.connect(second, browse, "Log")
    root = ET.fromstring(builder.render())
    nodes = root.find("Nodes")
    for container_id, members in ((first, (warning, deferred)), (second, (after,))):
        container = nodes.find(f"Node[@ToolID='{container_id}']")
        container.find("GuiSettings/Position").attrib.update(width="240", height="160")
        children = ET.SubElement(container, "ChildNodes")
        for member_id in members:
            member = nodes.find(f"Node[@ToolID='{member_id}']")
            nodes.remove(member)
            children.append(member)
    workflow = destination / "control-log.yxmd"
    ET.ElementTree(root).write(workflow, encoding="utf-8", xml_declaration=True)
    return [workflow]


def generate_fuzzy_key_samples(destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=False)
    paths = []
    for name, mode, values in (
        ("exact", "WholeField", ["Acme", "Acme", "Other", "ACME", "Acme "]),
        ("phone", "DigitsReverse", ["(123) 456-7890", "1234567890", "4123456789", "1-1234567890", "123456789"]),
    ):
        for merge in (False, True):
            builder = WorkflowBuilder()
            source = builder.add_text_input(
                ["id", "value", "source"],
                [[str(i), value, "A" if i in {2, 3} else "B"] for i, value in enumerate(values, 1)],
            )
            fuzzy = builder._node(
                "FuzzyMatch",
                f'<RecordIdField>id</RecordIdField><MatchThreshold value="80"/>'
                f'<OutputScore value="True"/><MergeMode value="{merge}"/><SourceIdField>source</SourceIdField>'
                '<MatchFields><MatchField><FieldName>value</FieldName><Style Name="Custom">'
                f'<KeyGeneration><KeyFunction>{mode}</KeyFunction><UseWords value="False"/>'
                '<IgnoreEmpty value="True"/><MaxKeyLen value="10"/></KeyGeneration>'
                '<Match><MatchFunction>None</MatchFunction><AdditionalMatchFunction>NoSpace</AdditionalMatchFunction>'
                '<MatchThreshold value="0"/><MatchWeight value="100"/></Match>'
                '</Style></MatchField></MatchFields>',
                (250, 180),
            )
            builder.connect(source, fuzzy)
            path = destination / f"fuzzy-{name}-{'merge' if merge else 'purge'}.yxmd"
            path.write_text(builder.render(), encoding="utf-8")
            paths.append(path)
    return paths


def generate_variable_event_sample(destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=False)
    script = destination / "record-event.cmd"
    script.write_bytes(b"@echo off\r\necho %~1>>events.txt\r\n")
    builder = WorkflowBuilder()
    source = builder.add_text_input(["x"], [["2"], ["5"]])
    formula = builder.add_formula([
        ("computed", "Int64", "8", "[x] * [User.rate]"),
        ("tag", "V_WString", "32", "[User.label]"),
    ])
    builder.connect(source, formula)
    root = ET.fromstring(builder.render())
    properties = root.find("Properties")
    constants = ET.SubElement(properties, "Constants")
    for namespace, name, value, numeric in (
        ("User", "rate", "3", "True"), ("User", "label", "parity", "False")
    ):
        constant = ET.SubElement(constants, "Constant")
        for field, item in (("Namespace", namespace), ("Name", name), ("Value", value)):
            ET.SubElement(constant, field).text = item
        ET.SubElement(constant, "IsNumeric", value=numeric)
    events = properties.find("Events")
    if events is None:
        events = ET.SubElement(properties, "Events")
    events.clear()
    ET.SubElement(events, "Enabled", value="True")
    for timing, marker in (("Before", "before"), ("AfterNoError", "success"), ("After", "after")):
        event = ET.SubElement(events, "Event")
        ET.SubElement(event, "When").text = timing
        ET.SubElement(event, "cmd_Program").text = script.name
        ET.SubElement(event, "cmd_CommandLine").text = marker
        ET.SubElement(event, "cmd_WorkingDir").text = "."
    workflow = destination / "variable-events.yxmd"
    ET.ElementTree(root).write(workflow, encoding="utf-8", xml_declaration=True)
    return [workflow]


def generate_container_macro_samples(destination: Path) -> list[Path]:
    """Author one graph with an on/off nested container and a nested macro."""
    destination.mkdir(parents=True, exist_ok=False)

    def macro(name, operation):
        root = ET.Element("AlteryxDocument", yxmdVer="2025.1")
        nodes = ET.SubElement(root, "Nodes")
        config = _node(nodes, 1, "MacroInput", "AlteryxMacroInput")
        ET.SubElement(config, "Name").text = "Input"
        ET.SubElement(config, "UseFileInput", value="False")
        ET.SubElement(config, "ShowFieldMap", value="False")
        template = ET.SubElement(ET.SubElement(config, "TextInput"), "Configuration")
        ET.SubElement(template, "NumRows", value="1")
        ET.SubElement(ET.SubElement(template, "Fields"), "Field", name="x")
        ET.SubElement(ET.SubElement(ET.SubElement(template, "Data"), "r"), "c").text = "1"
        operation(nodes)
        ET.SubElement(_node(nodes, 3, "MacroOutput", "AlteryxMacroOutput"), "Name").text = "Output"
        edges = ET.SubElement(root, "Connections")
        _edge(edges, 1, "Output", 2, "Input")
        _edge(edges, 2, "Output", 3, "Input")
        runtime = ET.SubElement(ET.SubElement(root, "Properties"), "RuntimeProperties")
        ET.SubElement(runtime, "ModuleType").text = "Macro"
        ET.ElementTree(root).write(destination / name, encoding="utf-8", xml_declaration=True)

    def multiply(nodes):
        fields = ET.SubElement(_node(nodes, 2, "Formula", "AlteryxFormula"), "FormulaFields")
        ET.SubElement(fields, "FormulaField", field="x", expression="[x] * 3", type="Int64", size="8")

    def call(nodes, tool_id, name):
        node = ET.SubElement(nodes, "Node", ToolID=str(tool_id))
        gui = ET.SubElement(node, "GuiSettings", Plugin="")
        ET.SubElement(gui, "Position", x="520", y="260")
        ET.SubElement(ET.SubElement(node, "Properties"), "Configuration")
        ET.SubElement(node, "EngineSettings", Macro=name)

    macro("Multiply.yxmc", multiply)
    macro("NestedMultiply.yxmc", lambda nodes: call(nodes, 2, "Multiply.yxmc"))
    builder = WorkflowBuilder()
    source = builder.add_text_input(["x"], [["1"], ["2"], ["5"]])
    transform = builder.add_formula([("x", "Int64", "8", "[x] + 1")], position=(250, 200))
    branch = builder.add_filter("[x] > 3", position=(400, 260))
    builder.connect(source, transform)
    builder.connect(transform, branch)
    root = ET.fromstring(builder.render())
    nodes = root.find("Nodes")
    branch_node = nodes.find(f"Node[@ToolID='{branch}']")
    nodes.remove(branch_node)

    def container(parent, tool_id, position):
        node = ET.SubElement(parent, "Node", ToolID=str(tool_id))
        gui = ET.SubElement(node, "GuiSettings", Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer")
        ET.SubElement(gui, "Position", **position)
        props = ET.SubElement(ET.SubElement(node, "Properties"), "Configuration")
        ET.SubElement(props, "Caption").text = f"Container {tool_id}"
        disabled = ET.SubElement(props, "Disabled", value="False")
        return ET.SubElement(node, "ChildNodes"), disabled

    outer, disabled = container(nodes, 4, {"x": "320", "y": "145", "width": "430", "height": "260"})
    inner, _ = container(outer, 5, {"x": "350", "y": "180", "width": "355", "height": "165"})
    inner.append(branch_node)
    call(inner, 6, "NestedMultiply.yxmc")
    _edge(root.find("Connections"), branch, "True", 6, "Input")
    paths = []
    for state in ("enabled", "disabled"):
        disabled.set("value", str(state == "disabled"))
        path = destination / f"container-{state}.yxmd"
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        paths.append(path)
    return paths


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
