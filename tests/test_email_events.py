from email import policy
from email.parser import BytesParser
from xml.etree import ElementTree as ET

import pytest

from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.workflow_events import workflow_events
from alteryx2python.workflow_generator import WorkflowBuilder


def mail_workflow(tmp_path, when='AfterNoError', encryption='TLS', authentication=False):
    builder = WorkflowBuilder()
    builder.add_text_input(['value'], [['2']])
    root = ET.fromstring(builder.render())
    properties = root.find('Properties')
    previous = properties.find('Events')
    if previous is not None:
        properties.remove(previous)
    event = ET.SubElement(ET.SubElement(properties, 'Events'), 'Event')
    for key, value in [('When', when), ('SendMail', 'True'), ('email_From', 'sender@example.invalid'),
                       ('email_To', 'recipient@example.invalid'), ('email_Subject', 'Workflow report'),
                       ('email_Body', 'Plain body\n<no markup>'), ('email_SMTPServer', 'smtp.example.invalid'),
                       ('email_Port', '587'), ('email_Encryption', encryption),
                       ('email_Authentication', str(authentication)),
                       ('email_Username', 'user' if authentication else '')]:
        ET.SubElement(event, key).text = value
    ET.SubElement(ET.SubElement(event, 'email_Attachments'), 'attachment').text = 'source.csv'
    return XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), tmp_path / 'mail.yxmd')


def test_native_singular_timing_and_disabled_event_aliases():
    for source, expected in [('AfterError', 'failure'), ('AfterNoError', 'success')]:
        events = workflow_events(f'<AlteryxDocument><Properties><Events><Event><When>{source}</When>'
            '<cmd_Program>python</cmd_Program><cmd_CommandArguments>--version</cmd_CommandArguments>'
            '</Event></Events></Properties></AlteryxDocument>')
        assert events[0]['when'] == expected
        assert events[0]['arguments'] == '--version'
    assert workflow_events('<AlteryxDocument><Properties><Events><Event><When>Disabled</When>'
        '</Event></Events></Properties></AlteryxDocument>') == []


def test_email_event_drafts_match_delivered_native_source(tmp_path):
    workflow = mail_workflow(tmp_path)
    (tmp_path / 'source.csv').write_text('value\n2\n', encoding='utf-8')
    baseline_dir, native_dir = tmp_path / 'canonical', tmp_path / 'native'
    context = WorkflowContext(runtime_config={'input_dir': str(tmp_path), 'output_dir': str(baseline_dir),
        'delivery_profile': 'html-draft-v1'})
    run_workflow_graph(workflow, context)
    artifact = ReadablePythonGenerator().generate(workflow, delivery_profile='html-draft-v1')
    assert 'alteryx2python' not in artifact.source
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.source, namespace)
    namespace['run_workflow'](input_dir=tmp_path, output_dir=native_dir)
    assert (baseline_dir / 'event-0.eml').read_bytes() == (native_dir / 'event-0.eml').read_bytes()
    message = BytesParser(policy=policy.default).parsebytes((native_dir / 'event-0.eml').read_bytes())
    assert message['X-Unsent'] == '1'
    assert message.get_body(preferencelist=('plain',)).get_content() == 'Plain body\r\n<no markup>\r\n'
    attachment = next(message.iter_attachments())
    assert attachment.get_filename() == 'source.csv'
    assert attachment.get_payload(decode=True) == (tmp_path / 'source.csv').read_bytes()
    assert context.diagnostics[-1]['sent'] is False


def test_mail_event_requires_explicit_profile(tmp_path):
    workflow = mail_workflow(tmp_path)
    with pytest.raises(NotImplementedError, match='explicit'):
        run_workflow_graph(workflow, WorkflowContext())
    with pytest.raises(UnsupportedLowering, match='explicit'):
        ReadablePythonGenerator().generate(workflow)


def test_email_event_attaches_relocated_current_sink_instead_of_stale_input(tmp_path):
    workflow = mail_workflow(tmp_path)
    workflow.source_xml = workflow.source_xml.replace('source.csv', 'report.csv')
    root = ET.fromstring(workflow.source_xml)
    builder = WorkflowBuilder()
    builder.add_csv_output('report.csv')
    sink = ET.fromstring(builder.nodes_xml[-1])
    sink.set('ToolID', '2')
    root.find('Nodes').append(sink)
    root.find('Connections').append(ET.fromstring('<Connection><Origin ToolID="1" Connection="Output"/>'
        '<Destination ToolID="2" Connection="Input"/></Connection>'))
    workflow = XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), tmp_path / 'mail.yxmd')
    (tmp_path / 'report.csv').write_text('STALE_REPORT', encoding='utf-8')
    for name in ['baseline', 'native']:
        output = tmp_path / name
        if name == 'baseline':
            run_workflow_graph(workflow, WorkflowContext(runtime_config={'input_dir': str(tmp_path),
                'output_dir': str(output), 'redirect_sinks': True, 'delivery_profile': 'html-draft-v1'}))
        else:
            artifact = ReadablePythonGenerator().generate(workflow, delivery_profile='html-draft-v1')
            namespace = {'__file__': str(tmp_path / 'native.py')}
            exec(artifact.source, namespace)
            namespace['run_workflow'](input_dir=tmp_path, output_dir=output)
        message = BytesParser(policy=policy.default).parsebytes((output / 'event-0.eml').read_bytes())
        attached = next(message.iter_attachments()).get_payload(decode=True)
        assert attached == (output / 'report.csv').read_bytes()
        assert b'STALE_REPORT' not in attached


def test_smtp_events_use_native_settings_and_environment_credentials(tmp_path, monkeypatch):
    (tmp_path / 'source.csv').write_text('value\n2\n', encoding='utf-8')
    for name in ['SMTP_HOST', 'SMTP_PORT', 'SMTP_SECURITY', 'SMTP_USERNAME', 'SMTP_PASSWORD']:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('SMTP_PASSWORD', 'test-password')
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, **kwargs):
            calls.append(('connect', host, port))
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def starttls(self, **kwargs):
            calls.append(('tls',))
        def login(self, username, password):
            calls.append(('login', username, password))
        def send_message(self, message):
            assert message['X-Unsent'] is None
            calls.append(('sent', message['Subject']))
            return {}

    monkeypatch.setattr('smtplib.SMTP', FakeSMTP)
    workflow = mail_workflow(tmp_path, authentication=True)
    run_workflow_graph(workflow, WorkflowContext(runtime_config={
        'input_dir': str(tmp_path), 'delivery_profile': 'html-smtp-v1'}))
    artifact = ReadablePythonGenerator().generate(workflow, delivery_profile='html-smtp-v1')
    namespace = {'__file__': str(tmp_path / 'native.py')}
    exec(artifact.source, namespace)
    namespace['run_workflow'](input_dir=tmp_path, output_dir=tmp_path / 'native')
    assert calls == [('connect', 'smtp.example.invalid', 587), ('tls',),
        ('login', 'user', 'test-password'), ('sent', 'Workflow report')] * 2


def test_mail_event_dcm_transport_remains_explicit_blocker(tmp_path):
    workflow = mail_workflow(tmp_path)
    workflow.source_xml = workflow.source_xml.replace('</Event>', '<Connection id="test"/></Event>')
    with pytest.raises(UnsupportedLowering, match='DCM'):
        ReadablePythonGenerator().generate(workflow, delivery_profile='html-smtp-v1')
