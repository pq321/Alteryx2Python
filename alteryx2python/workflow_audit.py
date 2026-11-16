"""Inventory migration gaps and optionally execute an isolated diagnostic run."""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from alteryx2python.expressions.errors import UnsupportedExpressionError
from alteryx2python.expressions.parser import SUPPORTED_FUNCTIONS, parse_expression
from alteryx2python.generator.macro_sources import resolve_macro_path
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.app_config import INTERFACE, SUPPORTED_ACTION_TYPES, _value, prepare_workflow
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.scheduling import container_guards, detour_exclusions
from alteryx2python.tools.registry import TOOL_REGISTRY


_CALLS = re.compile(r'''//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\[[^\]]*\]|(?P<call>\b[A-Za-z_]\w*)\s*(?=\()''')
_KEYWORDS = {'IF', 'ELSEIF', 'ELSE', 'THEN', 'AND', 'OR', 'NOT'}
_EXPRESSION_FIELDS = {
    'Filter': ('expression',), 'MultiFieldFormula': ('expression',), 'MultiRowFormula': ('expression',),
    'GenerateRows': ('expression_init', 'expression_cond', 'expression_loop'),
    'DynamicRename': ('expression',), 'DynamicSelect': ('expression',), 'DynamicReplace': ('field_expression',),
    'Message': ('filter', 'message_expression'), 'Condition': ('expression',), 'Error': ('expression',),
}


def feeds_control_log(node, by_id, edges):
    parent = node.config.get('container_id')
    while parent:
        container = by_id[parent]
        if container.tool_type == 'ControlContainer' and any(
            edge.source_node_id == parent and edge.source_anchor == 'Log' for edge in edges
        ):
            return True
        parent = container.config.get('container_id')
    return False


def diagnostic_message_only(node, config, by_id, edges, *, exposed=False):
    return (node.tool_type == 'Message' and (config.get('type') or 'Message').lower() == 'message' and
            (config.get('when') or 'First').lower() in {'first', 'last', 'filter', 'all'} and
            not exposed and not feeds_control_log(node, by_id, edges))


def audit_side_effect(tool_type, metadata):
    from alteryx2python.parity.runner import SIDE_EFFECT_TOOLS

    return (tool_type in SIDE_EFFECT_TOOLS - {'DynamicInput', 'BlobInput'} or metadata.execution_profile in {
        'local-local_runtimes', 'local-local_media', 'local-local_vision', 'local-indb',
    })


def review_message(metadata):
    def execute(inputs, config, context):
        try:
            if (config.get('when') or '').lower() == 'filter':
                parse_expression(config['filter'])
            parse_expression(config['message_expression'])
        except UnsupportedExpressionError as error:
            node_id = config['node_id']
            context.record_diagnostic({'kind': 'audit_gap', 'code': 'diagnostic_message_not_rendered',
                                       'node_id': node_id, 'message': str(error)})
            outputs = {'Output': inputs['Input'].copy()}
            context.record_node(node_id=node_id, source_tool_id=config['source_tool_id'], tool_type='Message',
                                inputs=inputs, outputs=outputs, status='diagnostic_deferred', config={})
            return outputs
        return metadata.function(inputs, config, context)

    return replace(metadata, function=execute)


def _event_checks(source_xml):
    from copy import deepcopy
    from alteryx2python.workflow_events import workflow_events

    events = ET.fromstring(source_xml).find('./Properties/Events') if source_xml else None
    if events is None:
        return
    probe = ET.Element('AlteryxDocument')
    isolated = ET.SubElement(ET.SubElement(probe, 'Properties'), 'Events')
    enabled = events.find('Enabled')
    for index, event in enumerate(events.findall('Event')):
        isolated[:] = [deepcopy(enabled), deepcopy(event)] if enabled is not None else [deepcopy(event)]
        try:
            parsed = workflow_events(ET.tostring(probe, encoding='unicode'))
        except (ValueError, NotImplementedError) as error:
            yield {'code': 'unsupported_workflow_event', 'event_id': str(index), 'message': str(error)}
        else:
            if parsed:
                yield {'code': 'event_not_run', 'event_id': str(index), 'when': parsed[0]['when']}


def audit_events(workflow, context):
    for gap in _event_checks(workflow.source_xml):
        context.record_diagnostic({'kind': 'audit_gap', **gap})


def _formula_issue(expression):
    calls = {match['call'].upper() for match in _CALLS.finditer(expression) if match['call']}
    missing = sorted(calls - _KEYWORDS - SUPPORTED_FUNCTIONS)
    if missing:
        return {'code': 'unregistered_expression_functions', 'functions': missing}
    try:
        parse_expression(expression)
    except (UnsupportedExpressionError, ValueError) as error:
        return {'code': 'expression_needs_review', 'message': str(error)}
    return None


def _expressions(node, config):
    if node.tool_type == 'Formula':
        for index, field in enumerate(config.get('formula_fields', ())):
            yield f'formula_fields[{index}].expression', field.get('expression')
    for field in _EXPRESSION_FIELDS.get(node.tool_type, ()):
        if field == 'filter' and (config.get('when') or '').lower() != 'filter':
            continue
        yield field, config.get(field)


def _inventory(workflow, call_path=(), parents=(), inactive=False, messages_exposed=False):
    by_id = {node.node_id: node for node in workflow.nodes}
    _, detour_skips = detour_exclusions(workflow.nodes, workflow.edges)
    for node in workflow.nodes:
        config = node.config.get('normalized', node.config)
        skipped = inactive or node.node_id in detour_skips or None in container_guards(node, by_id, workflow.edges)
        location = {'source': workflow.source_file, 'macro_call_path': list(call_path),
                    'node_id': node.node_id, 'tool_type': node.tool_type, 'active': not skipped}
        diagnostic_only = diagnostic_message_only(node, config, by_id, workflow.edges, exposed=messages_exposed)
        for field, expression in _expressions(node, config):
            if isinstance(expression, str) and expression.strip() and (issue := _formula_issue(expression)):
                yield {**location, **issue, 'field': field, 'impact': 'diagnostic' if diagnostic_only else 'execution'}
        if node.tool_type in INTERFACE:
            continue
        metadata = TOOL_REGISTRY._registry.get(node.tool_type)
        if node.tool_type.startswith('Macro_'):
            reference = config.get('macro_path', '')
            try:
                path = resolve_macro_path(reference, config.get('base_dir', Path(workflow.source_file).parent)) if reference else None
                if path is None or path in parents:
                    yield {**location, 'code': 'unresolved_macro', 'reference': reference}
                else:
                    child = XmlWorkflowParser().parse(path)
                    exposed = messages_exposed or feeds_control_log(node, by_id, workflow.edges)
                    yield from _inventory(child, (*call_path, node.node_id), (*parents, path), skipped, exposed)
            except (OSError, ValueError, ET.ParseError) as error:
                yield {**location, 'code': 'unreadable_macro', 'reference': reference, 'message': str(error)}
        elif metadata is None or metadata.execution_profile == 'unavailable':
            yield {**location, 'code': 'unsupported_tool'}

    if workflow.source_xml:
        root = ET.fromstring(workflow.source_xml)
        for gap in _event_checks(workflow.source_xml):
            if gap['code'] == 'unsupported_workflow_event':
                yield {**gap, 'source': workflow.source_file, 'macro_call_path': list(call_path), 'active': not inactive}
        record_limit = root.find('./Properties/GlobalRecordLimit')
        if record_limit is not None and record_limit.get('value', '').strip() not in {'', '0'}:
            yield {'source': workflow.source_file, 'macro_call_path': list(call_path), 'active': not inactive,
                   'code': 'unsupported_runtime_setting', 'field': 'GlobalRecordLimit', 'impact': 'execution'}
        actions = root.find('./Properties/RuntimeProperties/Actions')
        for owner in actions.iter() if actions is not None else ():
            location = {'source': workflow.source_file, 'macro_call_path': list(call_path),
                        'node_id': _value(owner, 'ToolId') or None, 'destination': _value(owner, 'Destination') or None,
                        'active': not inactive, 'impact': 'execution'}
            mode = _value(owner, 'Type')
            if owner.tag == 'Action' and mode not in SUPPORTED_ACTION_TYPES:
                yield {**location, 'code': 'unsupported_action_mode', 'mode': mode}
            expression = _value(owner, 'Expression').strip().replace('{{INPUT}}', '[__action_input__]')
            if expression and (issue := _formula_issue(expression)):
                yield {**location, **issue, 'field': 'RuntimeProperties/Actions/Expression'}


def audit_workflow(workflow, *, run=False, answers=None, runtime=None, parameter_mode='dynamic', delivery_profile=None):
    from alteryx2python.generator.readable import ReadablePythonGenerator
    from alteryx2python.runtime.executor import run_workflow_graph

    original = list(_inventory(workflow))
    issues = original
    prepared = None
    try:
        prepared = prepare_workflow(workflow, answers)
    except (KeyError, ValueError, NotImplementedError, UnsupportedExpressionError, ET.ParseError) as error:
        issues.append({'code': 'app_configuration_failed', 'message': str(error), 'active': True})
    else:
        issues = list(_inventory(prepared))
        issues.extend({**item, 'active': False, 'saved_only': True} for item in original if item not in issues)

    compilation = {'status': 'compiled'}
    try:
        ReadablePythonGenerator().generate(workflow, answers=answers, parameter_mode=parameter_mode,
                                           delivery_profile=delivery_profile,
                                           input_bindings=(runtime or {}).get('input_bindings'), collect_expression_issues=True)
    except (KeyError, ValueError, NotImplementedError, UnsupportedExpressionError, OSError, ET.ParseError) as error:
        compilation = {'status': 'blocked', 'issues': getattr(error, 'issues', None) or [{'reason': str(error)}]}

    execution = {'status': 'not_requested'}
    if run and prepared is None:
        execution = {'status': 'blocked_by_app_configuration'}
    elif run:
        with TemporaryDirectory(prefix='alteryx-audit-') as directory:
            context = WorkflowContext({**(runtime or {}), 'answers': answers, '_workflow_audit': True,
                                       'capture_output_dir': directory,
                                       'output_dir': directory, 'delivery_profile': delivery_profile})
            failure = None
            try:
                run_workflow_graph(prepared, context)
            except Exception as error:
                failure = {'type': type(error).__name__, 'message': str(error)}
            outcomes = {trace.node_id: {'node_id': trace.node_id, 'tool_type': trace.tool_type, 'status': trace.status,
                                       **{key: trace.config[key] for key in ('reason', 'error_message', 'blocked_by') if key in trace.config},
                                       'output_rows': {anchor: value.row_count for anchor, value in trace.outputs.items()}}
                        for trace in context.traces}
            execution = {'status': 'stopped' if failure else 'completed', 'failure': failure,
                         'nodes': [outcomes.get(node.node_id, {'node_id': node.node_id, 'tool_type': node.tool_type,
                                                             'status': 'not_run'}) for node in prepared.nodes],
                         'deferred_checks': [entry for entry in context.diagnostics if entry.get('kind') == 'audit_gap']}
    status = 'needs_review' if (any(item['active'] for item in issues) or compilation['status'] != 'compiled' or
                                execution.get('failure') or execution.get('deferred_checks') or
                                any(node['status'] in {'failed', 'blocked', 'not_run'} for node in execution.get('nodes', ()))) else 'completed'
    return {'command': 'audit', 'status': status, 'source': workflow.source_file,
            'inventory': issues, 'phase_two': compilation, 'execution': execution}
