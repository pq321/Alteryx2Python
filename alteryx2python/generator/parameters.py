"""Lower supported app actions to explicit Python parameters without interpretation."""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from xml.etree import ElementTree as ET

from alteryx2python.expressions.ast import ExpressionNode, LiteralExpression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.runtime.app_config import prepare_workflow, question_manifest


@dataclass(frozen=True)
class ParameterExpression(ExpressionNode):
    name: str


BOOLEAN_QUESTIONS = {'BooleanGroup', 'CheckBoxGroup', 'RadioGroup', 'RadioButtonGroup'}
TEXT_QUESTIONS = {'TextBox', 'QuestionTextBox', 'Date', 'DropDown', 'FileBrowse', 'QuestionFileBrowse', 'FolderBrowse'}


def _alternate(question, value):
    if question.kind == 'NumericUpDown':
        minimum = float(question.minimum) if question.minimum else None
        maximum = float(question.maximum) if question.maximum else None
        step = 1 if maximum is None or value + 1 <= maximum else -1
        alternate = value + step
        if minimum is not None and alternate < minimum:
            raise UnsupportedLowering(f'Question range is fixed: {question.name}')
        return alternate
    if question.kind in BOOLEAN_QUESTIONS:
        return not value
    if question.choices:
        return next((item for item in question.choices if item != value), value)
    if question.kind == 'Date':
        from datetime import date, timedelta
        return str(date.fromisoformat(value) + timedelta(days=1))
    if question.kind in {'FileBrowse', 'QuestionFileBrowse', 'FolderBrowse'}:
        from pathlib import PurePath
        path = PurePath(value or 'input.csv')
        return str(path.with_name('__parameter_probe__' + path.suffix))
    return '__parameter_probe__'


def _differences(left, right, path=()):
    if isinstance(left, dict) and isinstance(right, dict) and left.keys() == right.keys():
        return [change for key in left for change in _differences(left[key], right[key], (*path,key))]
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [change for index, value in enumerate(left) for change in _differences(value,right[index],(*path,index))]
    return [] if left == right else [(path, left, right)]


def _merge(current, base, changed, name, original_value, alternate_value):
    if type(base) is not type(changed):
        raise UnsupportedLowering(f'Question changes expression structure: {name}')
    if isinstance(base, LiteralExpression):
        if base.value == changed.value:
            return current
        if base.value != original_value or changed.value != alternate_value:
            raise UnsupportedLowering(f'Question needs a non-literal expression template: {name}')
        return ParameterExpression(name)
    if is_dataclass(base):
        updates = {}
        for field in fields(base):
            a,b,c = getattr(current,field.name),getattr(base,field.name),getattr(changed,field.name)
            if isinstance(b, ExpressionNode):
                updates[field.name] = _merge(a,b,c,name,original_value,alternate_value)
            elif isinstance(b,list):
                if len(b) != len(c):
                    raise UnsupportedLowering(f'Question changes function arity: {name}')
                updates[field.name] = [_merge(x,y,z,name,original_value,alternate_value) for x,y,z in zip(a,b,c)]
            elif b != c:
                raise UnsupportedLowering(f'Question changes an operator or field: {name}')
        return replace(current,**updates)
    raise UnsupportedLowering(f'Unsupported question action: {name}')


def prepare_parameters(workflow, answers):
    prepared = prepare_workflow(workflow, answers)
    questions = question_manifest(ET.fromstring(workflow.source_xml)) if workflow.source_xml else []
    expressions, specs, bindings = {}, [], []
    actual = prepared.metadata.get('answers', {})
    for question in questions:
        if question.kind not in {'NumericUpDown'} | BOOLEAN_QUESTIONS | TEXT_QUESTIONS:
            raise UnsupportedLowering(f'Runtime question type needs a dedicated parameter template: {question.kind}')
        value = actual[question.name]
        minimum = float(question.minimum) if question.minimum else None
        maximum = float(question.maximum) if question.maximum else None
        alternate = _alternate(question, value)
        actions = ET.fromstring(workflow.source_xml).find('Properties/RuntimeProperties/Actions')
        if actions is not None and any(item.tag == 'Condition' or item.tag == 'Action' and item.findtext('Type') not in {'UpdateValue', 'UpdateValueReplace', 'UpdateInput', 'UpdateOutput'} for item in actions.iter()):
            raise UnsupportedLowering('Conditional/formula/raw-XML Actions require a structural parameter template')
        variant = prepare_workflow(workflow, {**actual,question.name:alternate})
        before,after = {n.node_id:n for n in prepared.nodes},{n.node_id:n for n in variant.nodes}
        if before.keys() != after.keys() or prepared.edges != variant.edges:
            raise UnsupportedLowering(f'Question changes graph topology: {question.name}')
        changed_count = 0
        for node_id,node in before.items():
            for path,base,changed in _differences(node.config.get('normalized',node.config),after[node_id].config.get('normalized',after[node_id].config)):
                if node.tool_type == 'Filter' and path == ('expression',) or node.tool_type == 'Formula' and len(path) == 3 and path[0] == 'formula_fields' and path[2] == 'expression':
                    key = (node_id,path)
                    parsed = parse_expression(base)
                    expressions[key] = _merge(expressions.get(key,parsed), parsed, parse_expression(changed), question.name,value,alternate)
                elif node.tool_type in {'DbFileInput', 'DbFileOutput'} and path == ('file',):
                    if str(base) != str(value) or str(changed) != str(alternate):
                        raise UnsupportedLowering('File parameters must replace the complete configured path')
                    bindings.append({'node_id': node_id, 'path': list(path), 'name': question.name, 'kind': 'file'})
                elif node.tool_type == 'TextInput' and len(path) == 3 and path[0] == 'rows' and isinstance(path[1], int) and isinstance(path[2], int):
                    from alteryx2python.runtime.app_config import _serialize
                    if base != _serialize(value) or changed != _serialize(alternate):
                        raise UnsupportedLowering('TextInput parameters must replace a complete cell')
                    bindings.append({'node_id': node_id, 'path': list(path), 'name': question.name, 'kind': 'cell'})
                else:
                    raise UnsupportedLowering(f'Question {question.name} changes unsupported configuration {node.tool_type}/{path}')
                changed_count += 1
        if not changed_count:
            raise UnsupportedLowering(f'Question has no recognized editable action: {question.name}')
        specs.append({'name':question.name, 'kind':question.kind, 'default':value,'minimum':minimum,'maximum':maximum,
                      'required':question.required,'choices':list(question.choices), 'source_node_id':question.node_id,
                      'target_node_ids':sorted({node_id for node_id, node in before.items() if node.config != after[node_id].config})})
    seen = set()
    for binding in bindings:
        key = (binding['node_id'], tuple(binding['path']))
        if key in seen:
            raise UnsupportedLowering('Multiple questions overwrite the same configuration cell')
        seen.add(key)
    prepared.metadata['parameter_bindings'] = bindings
    return prepared, expressions, specs


def validation_lines(spec, name):
    """Emit ordinary validation code for one packaged question/action binding."""
    kind = spec['kind']
    lines = []
    if kind == 'NumericUpDown':
        lines += [f'{name} = float({name})', f'if not math.isfinite({name}):', f'    raise ValueError("Invalid numeric input: {name}")', f'{name} = int({name}) if {name}.is_integer() else {name}']
        for key, operator in [('minimum', '<'), ('maximum', '>')]:
            if spec[key] is not None:
                lines += [f'if {name} {operator} {spec[key]!r}:', f'    raise ValueError("Input outside {key}: {name}")']
    elif kind in BOOLEAN_QUESTIONS:
        lines += [f'if not isinstance({name}, bool):', f'    if str({name}).lower() not in ("true", "false", "1", "0", "yes", "no", ""):', f'        raise ValueError("Invalid boolean input: {name}")', f'    {name} = str({name}).lower() in ("true", "1", "yes")']
    else:
        lines += [f'{name} = "" if {name} is None else str({name})']
        if kind == 'Date':
            lines += [f'if {name}:', f'    date.fromisoformat({name})']
    if spec['required']:
        lines += [f'if {name} is None or {name} == "":', f'    raise ValueError("Required input: {name}")']
    if spec['choices']:
        lines += [f'if {name} not in {spec["choices"]!r}:', f'    raise ValueError("Invalid choice: {name}")']
    return lines
