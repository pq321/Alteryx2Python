import json
import sys
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from alteryx2python.cli import main
from alteryx2python.parity.samples import generate_container_macro_samples
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.workflow_audit import audit_workflow
from alteryx2python.workflow_generator import WorkflowBuilder


def test_audit_collects_gaps_and_runs_independent_branches(tmp_path, capsys):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [[3], [4]])
    info = builder._node('Message', '<When>First</When><Type>Message</Type>'
                         '<MessageExpression>UnknownLog([x])</MessageExpression>', (200, 100))
    bad = builder.add_formula([('y', 'Int64', '8', 'UnknownOne([x]) + UnknownTwo([x])')])
    downstream = builder.add_formula([('z', 'Int64', '8', '[y] * 2')])
    warning = builder._node('Message', '<When>First</When><Type>Warning</Type>'
                            '<MessageExpression>UnknownWarning([x])</MessageExpression>', (200, 200))
    independent = builder.add_formula([('z', 'Int64', '8', '[x] * 2')])
    command = builder._node('RunCommand', f'<ProgramName>{escape(sys.executable)}</ProgramName>', (200, 300))
    output = builder.add_csv_output(str(tmp_path / 'production.csv'))
    for edge in [(source, info), (source, bad), (bad, downstream), (source, warning), (info, independent), (independent, output)]:
        builder.connect(*edge)
    root = ET.fromstring(builder.render())
    events = ET.SubElement(root.find('Properties'), 'Events')
    ET.SubElement(events, 'Event', When='AfterRun', Command='legacy-report.bat')
    workflow = tmp_path / 'demo.yxmd'
    ET.ElementTree(root).write(workflow, encoding='utf-8')

    assert main(['audit', str(workflow), '--run']) == 2
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'needs_review'
    assert report['execution']['status'] == 'completed'
    inventory = {item['node_id']: item for item in report['inventory']}
    assert inventory[str(bad)]['functions'] == ['UNKNOWNONE', 'UNKNOWNTWO']
    assert inventory[str(info)]['impact'] == 'diagnostic'
    assert inventory[str(warning)]['impact'] == 'execution'
    assert {str(info), str(bad), str(warning)} <= {issue['node_id'] for issue in report['phase_two']['issues']}
    nodes = {node['node_id']: node for node in report['execution']['nodes']}
    assert nodes[str(info)]['status'] == 'diagnostic_deferred'
    assert nodes[str(independent)]['output_rows'] == {'Output': 2}
    assert nodes[str(bad)]['status'] == nodes[str(warning)]['status'] == 'failed'
    assert nodes[str(downstream)]['blocked_by'] == [str(bad)]
    assert nodes[str(command)]['reason'] == 'side_effect_not_run'
    assert nodes[str(output)]['status'] == 'success'
    assert not (tmp_path / 'production.csv').exists()
    assert {entry['code'] for entry in report['execution']['deferred_checks']} == {
        'diagnostic_message_not_rendered', 'event_not_run',
    }


def test_audit_still_honors_explicit_workflow_cancellation(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [[2]])
    error = builder._node('Message', '<When>First</When><Type>ErrorStop</Type>'
                          '<MessageExpression>"stop"</MessageExpression>', (200, 100))
    blocked = builder.add_formula([('later', 'Int64', '8', 'StillUnknown([x])')])
    builder.connect(source, error)
    builder.connect(error, blocked)
    root = ET.fromstring(builder.render())
    ET.SubElement(root.find('Properties'), 'CancelOnError', value='True')
    workflow = XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), tmp_path / 'stop.yxmd')

    report = audit_workflow(workflow, run=True)
    assert report['execution']['status'] == 'stopped'
    assert report['execution']['failure']['message'] == 'stop'
    assert report['execution']['nodes'][-1]['status'] == 'not_run'
    assert report['inventory'][0]['functions'] == ['STILLUNKNOWN']


def test_audit_follows_nested_macro_call_paths_and_inactive_containers(tmp_path):
    enabled, disabled = generate_container_macro_samples(tmp_path / 'cases')
    child_path = enabled.parent / 'Multiply.yxmc'
    macro = ET.parse(child_path)
    macro.find('.//FormulaField').set('expression', 'UndefinedMacroFunction([x])')
    macro.write(child_path, encoding='utf-8')

    parser = XmlWorkflowParser()
    for path, active in [(enabled, True), (disabled, False)]:
        report = audit_workflow(parser.parse(path), run=True)
        item = next(item for item in report['inventory'] if item.get('functions') == ['UNDEFINEDMACROFUNCTION'])
        assert item['active'] == active
        assert item['macro_call_path'] == ['6', '2']
        assert item['node_id'] == '2'
        outcomes = {node['node_id']: node['status'] for node in report['execution']['nodes']}
        assert outcomes['2'] == 'success'
        assert outcomes['6'] == ('failed' if active else 'skipped')
        gaps = report['execution']['deferred_checks']
        assert any(gap['code'] == 'macro_node_incomplete' and gap['macro_call_path'] == ['6', '2'] for gap in gaps) == active


def test_audit_lists_multiple_action_and_event_gaps_after_binding_fails(tmp_path):
    builder = WorkflowBuilder()
    builder.add_text_input(['x'], [[2]])
    root = ET.fromstring(builder.render())
    properties = root.find('Properties')
    actions = properties.find('RuntimeProperties/Actions')
    actions.clear()
    for index in [10, 11]:
        action = ET.SubElement(actions, 'Action', ToolId=str(index))
        ET.SubElement(action, 'Type').text = f'UnknownAction{index}'
    events = ET.SubElement(properties, 'Events')
    for index in [0, 1]:
        ET.SubElement(events, 'Event', EventType=f'UnknownEvent{index}', When='BeforeRun')
    workflow = XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), tmp_path / 'unbound.yxwz')

    report = audit_workflow(workflow, run=True)
    assert {item['node_id'] for item in report['inventory'] if item['code'] == 'unsupported_action_mode'} == {'10', '11'}
    assert {item['event_id'] for item in report['inventory'] if item['code'] == 'unsupported_workflow_event'} == {'0', '1'}
    assert report['execution']['status'] == 'blocked_by_app_configuration'
