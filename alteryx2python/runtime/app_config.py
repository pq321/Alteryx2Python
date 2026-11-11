"""Bind native RuntimeProperties questions/actions before data graph execution."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

from alteryx2python.expressions.parser import parse_expression
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.tools.unavailable import ToolUnavailableError

LAYOUT = {"Tab", "Label", "LabelGroup", "Link", "MacroInput", "MacroOutput"}
INTERFACE = {
    "Action",
    "Condition",
    "Error",
    "ControlParam",
    "CheckBoxGroup",
    "Date",
    "DropDown",
    "FolderBrowse",
    "ListBox",
    "Map",
    "NumericUpDown",
    "QuestionFileBrowse",
    "QuestionTextBox",
    "RadioButtonGroup",
    "Tree",
    "Label",
    "LabelGroup",
    "Link",
    "QuestionTab",
}


def _root(source):
    if isinstance(source, ET.Element):
        return source
    if isinstance(source, Path):
        return ET.parse(source).getroot()
    return ET.fromstring(source)


def _value(node, key, default=""):
    element = node.find(key)
    if element is None:
        return node.get(key, default)
    return element.text if element.text is not None else element.get("value", default)


@dataclass(frozen=True)
class Question:
    name: str
    kind: str
    default: object = ""
    required: bool = False
    choices: tuple[str, ...] = ()
    node_id: str = ""
    minimum: str = ""
    maximum: str = ""


def question_manifest(root):
    runtime = root.find("./Properties/RuntimeProperties/Questions")
    if runtime is None:
        runtime = root.find("Questions")
    if runtime is None:
        return []
    questions = []
    for element in runtime.iter():
        if element.tag in {"Questions", "Type", "Default"}:
            continue
        kind = _value(element, "Type") if element.tag == "Question" else element.tag
        if kind in LAYOUT or kind not in {
            "TextBox",
            "QuestionTextBox",
            "NumericUpDown",
            "BooleanGroup",
            "CheckBoxGroup",
            "RadioGroup",
            "RadioButtonGroup",
            "Date",
            "DropDown",
            "ListBox",
            "FileBrowse",
            "QuestionFileBrowse",
            "FolderBrowse",
            "ControlParam",
            "Map",
            "Tree",
        }:
            continue
        name = _value(element, "Name")
        if not name:
            raise ValueError("Question must have a Name")
        choices = []
        manual = _value(element, "Manual_Values")
        for row in manual.splitlines():
            if row:
                choices.append(row.split(":", 1)[-1])
        choices.extend(x.text for x in element.findall("Option") if x.text is not None)
        questions.append(
            Question(
                name,
                kind,
                _value(element, "Default", _value(element, "DefaultValue")),
                str(_value(element, "Required", "false")).lower() in {"true", "1"},
                tuple(choices),
                _value(element, "ToolId", element.get("ToolID", "")),
                _value(element, "Min", _value(element, "Minimum")),
                _value(element, "Max", _value(element, "Maximum")),
            )
        )
    if len({q.name for q in questions}) != len(questions):
        raise ValueError("Question names must be unique")
    return questions


def list_questions(source):
    return question_manifest(_root(source))


def _typed(question, value):
    kind = question.kind
    if question.required and (value is None or value == "" or value == []):
        raise ValueError(f"required question has no answer: {question.name}")
    if kind == "NumericUpDown":
        try:
            number = float(value)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"numeric answer required: {question.name}") from exc
        if not math.isfinite(number):
            raise ValueError("Numeric question answer must be finite")
        if (
            question.minimum
            and number < float(question.minimum)
            or question.maximum
            and number > float(question.maximum)
        ):
            raise ValueError(f"answer outside numeric bounds: {question.name}")
        value = int(number) if number.is_integer() else number
    elif kind in {"BooleanGroup", "CheckBoxGroup", "RadioGroup", "RadioButtonGroup"}:
        if isinstance(value, bool):
            pass
        elif str(value).lower() in {"true", "1", "yes"}:
            value = True
        elif str(value).lower() in {"false", "0", "no", ""}:
            value = False
        else:
            raise ValueError(f"boolean answer required: {question.name}")
    elif kind == "ListBox":
        if not isinstance(value, list):
            import csv

            value = next(csv.reader([str(value)])) if value else []
    elif kind == "Date" and value:
        date.fromisoformat(str(value))
    elif kind in {"Map", "Tree"} and value:
        raise ToolUnavailableError(
            f"{kind} geometry/tree selection needs a specific value adapter"
        )
    if question.choices:
        selected = value if isinstance(value, list) else [value]
        if any(str(item) not in question.choices for item in selected):
            raise ValueError(f"invalid choice for {question.name}: {value}")
    return value


def _serialize(value):
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, list):
        import csv, io

        stream = io.StringIO()
        csv.writer(stream, lineterminator="").writerow(value)
        return stream.getvalue()
    return "" if value is None else str(value)


def bind_answers(root, answers=None):
    answers = answers or {}
    questions = question_manifest(root)
    names = {q.name for q in questions} | {q.node_id for q in questions if q.node_id}
    unknown = set(answers) - names
    if unknown:
        raise ValueError(f"Unknown question answers: {sorted(unknown)}")
    values = {
        q.name: _typed(q, answers.get(q.name, answers.get(q.node_id, q.default)))
        for q in questions
    }
    return deepcopy(root), values


def _expression(expression, values):
    try:
        return evaluate_expression(parse_expression(expression), values)
    except (NotImplementedError, SyntaxError) as exc:
        raise ToolUnavailableError(
            f"Action expression is not supported: {expression}"
        ) from exc


def _destination(root, path):
    if "/" not in path or not path.split("/", 1)[0].isdigit():
        raise ToolUnavailableError(f"Unsupported native Action destination: {path}")
    tool, location = path.split("/", 1)
    attribute = None
    if "/@" in location:
        location, attribute = location.rsplit("/@", 1)
    config = root.find(f".//Node[@ToolID='{tool}']/Properties/Configuration")
    if config is None:
        raise ValueError(f"Action target tool not found: {tool}")
    targets = config.findall(location)
    if not targets:
        raise ValueError(f"Action destination not found: {path}")
    return targets, attribute


def apply_actions(root, values):
    out = deepcopy(root)
    actions = out.find("./Properties/RuntimeProperties/Actions")
    if actions is None:
        return out

    def apply(action):
        mode = _value(action, "Type")
        if mode == "Error":
            if bool(_expression(_value(action, "Expression"), values)):
                raise ValueError(_value(action, "Description", "App validation failed"))
            return
        if mode in {"UpdateInput", "UpdateOutput"}:
            variable = _value(action, "Variable")
            tool = _value(
                action, "InputTool" if mode == "UpdateInput" else "OutputTool"
            )
            if variable not in values or not tool.isdigit() or int(tool) < 1:
                raise ToolUnavailableError(
                    "File Action requires an explicit question variable and target tool ID"
                )
            target = out.find(
                f".//Node[@ToolID='{tool}']/Properties/Configuration/File"
            )
            if target is None:
                raise ValueError("File Action target has no File configuration")
            replacement = _serialize(values[variable])
            if (
                not replacement
                and str(_value(action, "Required", "false")).lower() == "true"
            ):
                raise ValueError("File Action requires a path")
            old_extension = Path((target.text or "").split("|||", 1)[0]).suffix.lower()
            new_extension = Path(replacement.split("|||", 1)[0]).suffix.lower()
            if old_extension != new_extension:
                raise ToolUnavailableError(
                    "File Action format changes require explicit format configuration"
                )
            target.text = replacement
            return
        if mode == "UpdateSelect":
            # Selection answers arrive as a delimited field list; mark the
            # target Select node's SelectField entries accordingly.
            variable = _value(action, "Variable")
            if variable not in values:
                raise ToolUnavailableError(
                    f"Action variable has no bound question: {variable!r}"
                )
            selected_names = {
                item.strip()
                for item in str(_serialize(values[variable])).replace(";", ",").split(",")
                if item.strip()
            }
            tool = _value(action, "Destination").split("/", 1)[0]
            select_fields = out.find(
                f".//Node[@ToolID='{tool}']/Properties/Configuration/SelectFields"
            )
            if select_fields is None:
                raise ValueError(f"UpdateSelect target has no SelectFields: {tool}")
            for select_field in select_fields.findall("SelectField"):
                name = select_field.get("field", "")
                if name.startswith("*"):
                    continue
                select_field.set("selected", "True" if name in selected_names else "False")
            return
        if mode == "UpdateFieldList":
            # Replace the target field-list configuration wholesale.
            variable = _value(action, "Variable")
            if variable not in values:
                raise ToolUnavailableError(
                    f"Action variable has no bound question: {variable!r}"
                )
            entries = values[variable]
            if not isinstance(entries, (list, tuple)):
                entries = [
                    item.strip() for item in str(entries).replace(";", ",").split(",") if item.strip()
                ]
            tool = _value(action, "Destination").split("/", 1)[0]
            config_node = out.find(
                f".//Node[@ToolID='{tool}']/Properties/Configuration"
            )
            if config_node is None:
                raise ValueError(f"UpdateFieldList target tool not found: {tool}")
            for old_list in list(config_node):
                if old_list.tag.endswith("Fields"):
                    config_node.remove(old_list)
            fields_element = ET.SubElement(config_node, "Fields")
            for entry in entries:
                field_element = ET.SubElement(fields_element, "Field")
                field_element.set("field", str(entry))
                field_element.set("selected", "True")
            return
        if mode == "EditExpression":
            # Set the target expression text to the evaluated string.
            value = _expression(_value(action, "Expression"), values)
            targets, attribute = _destination(out, _value(action, "Destination"))
            for target in targets:
                if attribute:
                    target.set(attribute, _serialize(value))
                else:
                    target.text = _serialize(value)
            return
        if mode == "UpdateMap":
            # Map answers are spatial Extent serializations; record the value
            # into the target map configuration element.
            variable = _value(action, "Variable")
            if variable not in values:
                raise ToolUnavailableError(
                    f"Action variable has no bound question: {variable!r}"
                )
            targets, attribute = _destination(out, _value(action, "Destination"))
            replacement = _serialize(values[variable])
            for target in targets:
                if attribute:
                    target.set(attribute, replacement)
                else:
                    target.text = replacement
            return
        if mode == "DeleteTool":
            variable = _value(action, "Variable")
            delete = str(_serialize(values.get(variable, "False"))).lower() in {"true", "1"}
            if not delete:
                return
            tool = _value(action, "Destination").split("/", 1)[0]
            for parent in out.iter():
                for child in list(parent):
                    if child.tag == "Node" and child.get("ToolID") == tool:
                        parent.remove(child)
            connections = out.find("./Connections")
            if connections is not None:
                for connection in list(connections):
                    origin, destination = connection.find("Origin"), connection.find("Destination")
                    if (origin is not None and origin.get("ToolID") == tool) or (
                        destination is not None and destination.get("ToolID") == tool
                    ):
                        connections.remove(connection)
            return
        if mode == "DynamicAction":
            # Data-driven runtime actions cannot be evaluated statically; the
            # engine resolves them per record batch. Record explicitly.
            raise ToolUnavailableError(
                "DynamicAction is data-driven and has no static Python mapping"
            )
        if mode not in {
            "UpdateValue",
            "UpdateValueReplace",
            "UpdateValueFormula",
            "UpdateRawXml",
        }:
            raise ToolUnavailableError(f"unsupported Action mode: {mode}")
        if mode in {"UpdateValueFormula", "UpdateRawXml"}:
            value = _expression(_value(action, "Expression"), values)
        else:
            variable = _value(action, "Variable")
            if variable not in values:
                raise ToolUnavailableError(
                    f"Action variable has no bound question: {variable!r}"
                )
            value = values[variable]
        targets, attribute = _destination(out, _value(action, "Destination"))
        replacement = _serialize(value)
        for target in targets:
            if mode == "UpdateRawXml":
                if (
                    attribute
                    or str(_value(action, "OuterXml", "False")).lower() == "true"
                ):
                    raise ToolUnavailableError(
                        "UpdateRawXml OuterXml requires a specific adapter"
                    )
                content = ET.fromstring("<content>" + replacement + "</content>")
                target[:] = list(content)
                target.text = content.text
            else:
                old = target.get(attribute, "") if attribute else target.text or ""
                if (
                    mode == "UpdateValueReplace"
                    or str(_value(action, "Replace", "False")).lower() == "true"
                ):
                    token = _value(action, "ReplaceText")
                    if not token or token not in old:
                        raise ValueError("Action replacement token is empty or absent")
                    replacement = old.replace(token, _serialize(value))
                if attribute:
                    target.set(attribute, replacement)
                else:
                    target.text = replacement

    def walk(group):
        for child in group:
            if child.tag == "Action":
                apply(child)
            elif child.tag == "NoCondition":
                branch = child.find("True")
                if branch is not None:
                    walk(branch)
            elif child.tag == "Condition":
                condition = bool(_expression(_value(child, "Expression"), values))
                branch = child.find("True" if condition else "False")
                if branch is not None:
                    walk(branch)
            elif child.tag not in {"Type", "Description", "ToolId"}:
                raise ToolUnavailableError(f"Unsupported Action group: {child.tag}")

    walk(actions)
    return out


def configure_workflow(source, answers=None, *, apply=True):
    bound, values = bind_answers(_root(source), answers)
    configured = apply_actions(bound, values) if apply else bound
    for q in configured.findall("./Properties/RuntimeProperties/Questions//Question"):
        if _value(q, "Name") in values:
            default = q.find("Default")
            if default is None:
                default = ET.SubElement(q, "Default")
            if "value" in default.attrib:
                default.set("value", _serialize(values[_value(q, "Name")]))
            else:
                default.text = _serialize(values[_value(q, "Name")])
    return configured, values


def compile_workflow(source, answers=None):
    """Emit a configured data workflow; do not leave Actions to execute twice."""
    from alteryx2python.parser.xml_parser import XmlWorkflowParser

    configured, values = configure_workflow(source, answers)
    parsed = XmlWorkflowParser().parse_xml(
        ET.tostring(configured, encoding="unicode"), Path("configured.yxmd")
    )
    removed = {node.node_id for node in parsed.nodes if node.tool_type in INTERFACE}
    for parent in configured.iter():
        for child in list(parent):
            if child.tag == "Node" and child.get("ToolID") in removed:
                parent.remove(child)
    connections = configured.find("Connections")
    if connections is not None:
        for connection in list(connections):
            origin, destination = (
                connection.find("Origin"),
                connection.find("Destination"),
            )
            if (
                origin is not None
                and destination is not None
                and (
                    origin.get("ToolID") in removed
                    or destination.get("ToolID") in removed
                    or destination.get("Connection")
                    in {"Action", "Question", "Q", "Condition"}
                )
            ):
                connections.remove(connection)
    runtime = configured.find("Properties/RuntimeProperties")
    if runtime is not None:
        for element in list(runtime):
            if element.tag in {"Actions", "Questions", "BatchMacro"}:
                runtime.remove(element)
        module_type = runtime.find("ModuleType")
        if module_type is not None and module_type.text != "Macro":
            module_type.text = "Standard"
    return configured, values


def prepare_workflow(workflow, answers=None):
    """Reparse only affected tool configs; keep caller runtime overrides on others."""
    if not workflow.source_xml or workflow.metadata.get("configuration_applied"):
        return workflow
    from alteryx2python.parser.xml_parser import XmlWorkflowParser

    original = _root(workflow.source_xml)
    configured, values = configure_workflow(original, answers)
    result = XmlWorkflowParser().parse_xml(
        ET.tostring(configured, encoding="unicode"), Path(workflow.source_file)
    )
    source_nodes = {n.get("ToolID"): n for n in original.iter("Node")}
    changed_nodes = {n.get("ToolID"): n for n in configured.iter("Node")}
    previous = {n.node_id: n for n in workflow.nodes}
    for index, node in enumerate(result.nodes):
        a = source_nodes[node.node_id].find("Properties/Configuration")
        b = changed_nodes[node.node_id].find("Properties/Configuration")
        if (ET.tostring(a) if a is not None else b"") == (
            ET.tostring(b) if b is not None else b""
        ):
            result.nodes[index] = deepcopy(previous[node.node_id])
    result.nodes = [n for n in result.nodes if n.tool_type not in INTERFACE]
    active = {n.node_id for n in result.nodes}
    result.edges = [
        e
        for e in result.edges
        if e.source_node_id in active
        and e.target_node_id in active
        and e.target_anchor not in {"Action", "Question", "Q", "Condition"}
    ]
    result.source_hash = workflow.source_hash
    result.metadata = {
        **workflow.metadata,
        "configuration_applied": True,
        "answers": values,
    }
    result.warnings.append(
        "parameter_manifest=" + json.dumps(values, ensure_ascii=False)
    )
    return result
