"""Isolated file adapters for Designer migration cases."""

from collections import deque
import hashlib
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from alteryx2python.comparison.workbook import workbook_snapshot
from alteryx2python.workflow_generator import WorkflowBuilder

from .snapshot import encode_value


def formula_text(value):
    return '"' + str(value).replace('"', r'\"') + '"'


def field_reference(name):
    if not name or any(char in name for char in "[]\r\n"):
        raise ValueError(f"Cannot reference field in an isolation formula: {name!r}")
    return f"[{name}]"


_FORMULA_CLOCK = re.compile(
    r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\[[^\]]*\]|/\*.*?\*/|//[^\n]*|(?<![\w.])(?P<clock>DateTimeNow|DateTimeToday)\s*\(\s*\))''',
    re.IGNORECASE | re.DOTALL,
)


def bind_formula_clock(root, as_of):
    for field in root.findall(".//FormulaFields/FormulaField"):
        expression = field.get("expression")
        if not expression:
            continue

        def replace(match):
            clock = match.group("clock")
            if clock is None:
                return match.group()
            if clock.lower() == "datetimetoday":
                return f'DateTimeParse("{as_of[:10]}", "%Y-%m-%d")'
            return f'DateTimeParse("{as_of}", "%Y-%m-%d %H:%M:%S")'

        field.set("expression", _FORMULA_CLOCK.sub(replace, expression))


def insert_input_formula(root, target_id, new_id, field, expression):
    connections = root.find("Connections")
    inputs = [
        connection for connection in connections.findall("Connection")
        if connection.find("Destination").get("ToolID") == target_id
        and connection.find("Destination").get("Connection") == "Input"
    ]
    if len(inputs) != 1:
        raise ValueError(f"Tool {target_id} requires one Input connection for isolation")
    parent = next(
        parent for parent in root.iter()
        if parent.tag in {"Nodes", "ChildNodes"}
        and any(node.get("ToolID") == target_id for node in parent.findall("Node"))
    )
    builder = WorkflowBuilder(next_tool_id=new_id)
    builder.add_formula([(field, "V_WString", "65536", expression)])
    parent.append(ET.fromstring(builder.nodes_xml[-1]))
    inputs[0].find("Destination").set("ToolID", str(new_id))
    edge = ET.SubElement(connections, "Connection")
    ET.SubElement(edge, "Origin", ToolID=str(new_id), Connection="Output")
    ET.SubElement(edge, "Destination", ToolID=target_id, Connection="Input")


def report_projection_nodes(workflow, skipped):
    pending = deque(
        node.node_id for node in workflow.nodes
        if node.tool_type in {"PortfolioComposerTable", "PortfolioComposerLayout"}
        and node.node_id not in skipped
    )
    downstream = {}
    for edge in workflow.edges:
        downstream.setdefault(edge.source_node_id, []).append(edge.target_node_id)
    found = set()
    while pending:
        node_id = pending.popleft()
        if node_id in found:
            continue
        found.add(node_id)
        pending.extend(downstream.get(node_id, ()))
    return found


def project_report_snapshot(snapshot):
    """Compare tabular fields separately from the engine-specific report fragments."""
    indexes = [index for index, name in enumerate(snapshot["columns"]) if name not in {"Table", "Layout"}]
    projected = {**snapshot, "rows": [[row[index] for index in indexes] for row in snapshot["rows"]]}
    for key in ("columns", "python_dtypes"):
        if isinstance(snapshot.get(key), list):
            projected[key] = [snapshot[key][index] for index in indexes]
    if isinstance(snapshot.get("schema"), list):
        projected["schema"] = [field for field in snapshot["schema"] if field.get("name") in projected["columns"]]
    return projected


def workbook_artifacts(directory):
    return {
        path.name: workbook_digest(path)
        for path in sorted(Path(directory).glob("*.xlsx")) if path.is_file()
    }


def workbook_digest(path):
    payload = [
        (sheet, [[(kind, encode_value(value)) for kind, value in row] for row in rows])
        for sheet, rows in workbook_snapshot(path).items()
    ]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()


def isolated_workbook_name(label):
    return f"report-{hashlib.md5(label.encode('utf-8'), usedforsecurity=False).hexdigest()}.xlsx"
