"""Resolve workflow variables with explicit, nested execution scopes."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import math
import re
from xml.etree import ElementTree as ET

from alteryx2python.engine_variables import engine_constants, TEMP_TOKEN


ACTIVE_VARIABLES = ContextVar('alteryx_workflow_variables', default={})
TOKEN = re.compile(r'(?<!\[)%(Engine|User|Global|Question)\.([^%]+)%')


def workflow_variables(workflow, overrides=None):
    values = {'Engine.' + name: value for name, value in engine_constants(workflow.source_file).items()}
    if workflow.source_xml:
        root = ET.fromstring(workflow.source_xml)
        for item in root.findall('./Properties/Constants/Constant'):
            namespace = item.findtext('Namespace', 'User')
            name = item.findtext('Name', '')
            if not name:
                raise ValueError('Workflow constant has no name')
            if namespace == 'Question':
                continue
            value = item.findtext('Value', '')
            numeric = item.find('IsNumeric')
            if numeric is not None and numeric.get('value', numeric.text or '').lower() in {'true', '1'}:
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError(f'Workflow constant must be finite: {name}')
                value = int(value) if value.is_integer() else value
            key = namespace + '.' + name
            if key in values and namespace != 'Engine':
                raise ValueError(f'Duplicate workflow constant: {key}')
            values[key] = value
    values.update({'Question.' + name: value for name, value in workflow.metadata.get('answers', {}).items()})
    for name, value in (overrides or {}).items():
        if name not in values:
            raise ValueError(f'Unknown workflow constant override: {name}')
        if not isinstance(value, (str, int, float, bool)) or isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f'Invalid workflow constant override: {name}')
        values[name] = value
    return values


def resolve_variable_tokens(value, variables):
    if isinstance(value, str):
        def replace(match):
            name = match.group(1) + '.' + match.group(2)
            if name not in variables:
                raise ValueError(f'Unresolved workflow variable: {name}')
            return str(variables[name])
        value = TOKEN.sub(replace, value)
        return TEMP_TOKEN.sub(lambda match: str(variables['Engine.TempFilePath']), value)
    if isinstance(value, list):
        return [resolve_variable_tokens(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: resolve_variable_tokens(item, variables) for key, item in value.items()}
    return value


def bind_workflow_variables(workflow, overrides=None):
    result = deepcopy(workflow)
    values = workflow_variables(result, overrides)
    for node in result.nodes:
        node.config = resolve_variable_tokens(node.config, values)
        node.metadata['workflow_constants'] = values
    result.metadata['workflow_constants'] = values
    return result


@contextmanager
def variable_scope(values):
    token = ACTIVE_VARIABLES.set(values)
    try:
        yield
    finally:
        ACTIVE_VARIABLES.reset(token)
