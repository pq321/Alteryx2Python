import smtplib

import pandas as pd
import pytest

from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.tools.delivery import send_email
from alteryx2python.workflow_generator import WorkflowBuilder


@pytest.fixture
def smtp_transport(monkeypatch):
    calls, messages = [], []

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, **kwargs):
            calls.append(('starttls',))

        def login(self, username, password):
            calls.append(('login', username, password))

        def send_message(self, message):
            messages.append(message)
            return {}

    def connect(host, port, **kwargs):
        calls.append(('connect', host, port))
        return Client()

    monkeypatch.setattr(smtplib, 'SMTP', connect)
    monkeypatch.setattr(smtplib, 'SMTP_SSL', connect)
    for name, value in {'SMTP_HOST': 'smtp.example.test', 'SMTP_PORT': '587',
                        'SMTP_USERNAME': 'fixture-user', 'SMTP_PASSWORD': 'fixture-password',
                        'SMTP_SECURITY': 'starttls'}.items():
        monkeypatch.setenv(name, value)
    return calls, messages, Client


@pytest.mark.parametrize('security', ['starttls', 'ssl', 'plain'])
def test_smtp_transport_preserves_message_and_attachment(tmp_path, smtp_transport, monkeypatch, security):
    calls, messages, _ = smtp_transport
    monkeypatch.setenv('SMTP_SECURITY', security)
    attachment = tmp_path / 'report.csv'
    attachment.write_text('value\n3\n', encoding='utf-8')
    send_email(pd.DataFrame({'Report': ['<table><tr><td>3</td></tr></table>']}),
               'sender@example.test', 'recipient@example.test', 'Report', 'Report', [attachment])
    assert calls[0] == ('connect', 'smtp.example.test', 587)
    assert (('starttls',) in calls) == (security == 'starttls')
    assert calls[-1] == ('login', 'fixture-user', 'fixture-password')
    assert messages[0]['X-Unsent'] is None
    assert messages[0]['To'] == 'recipient@example.test'
    assert list(messages[0].iter_attachments())[0].get_payload(decode=True) == attachment.read_bytes()


def test_smtp_refusal_propagates_without_retry(smtp_transport, monkeypatch):
    calls, messages, client = smtp_transport
    monkeypatch.setattr(client, 'send_message', lambda self, message: {'bad@example.test': (550, b'Rejected')})
    with pytest.raises(smtplib.SMTPRecipientsRefused):
        send_email(pd.DataFrame({'Report': ['report']}), 'a@example.test', 'bad@example.test', 'Report', 'Report', [])
    assert len([call for call in calls if call[0] == 'connect']) == 1


def test_missing_smtp_configuration_never_connects(smtp_transport, monkeypatch):
    calls, _, _ = smtp_transport
    monkeypatch.delenv('SMTP_HOST')
    with pytest.raises(ValueError, match='SMTP_HOST'):
        send_email(pd.DataFrame({'Report': ['report']}), 'a@example.test', 'b@example.test', 'Report', 'Report', [])
    assert not calls


def test_smtp_workflow_native_source_uses_same_transport(tmp_path, smtp_transport):
    _, messages, _ = smtp_transport
    builder = WorkflowBuilder()
    source = builder.add_text_input(['Report'], [['<b>daily report</b>']])
    email = builder._node('Email', '', (1, 0))
    builder.connect(source, email)
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'mail.yxmd')
    node = next(node for node in workflow.nodes if node.node_id == str(email))
    node.config['normalized'] = {'from': 'a@example.test', 'to': 'b@example.test', 'subject': 'Daily report', 'body': 'Report'}
    artifact = ReadablePythonGenerator().generate(workflow, delivery_profile='html-smtp-v1')
    run_workflow_graph(workflow, WorkflowContext(runtime_config={'delivery_profile': 'html-smtp-v1', 'output_dir': str(tmp_path)}))
    namespace = {'__file__': str(tmp_path / 'native.py')}
    exec(artifact.source, namespace)
    namespace['run_workflow'](output_dir=tmp_path / 'output')
    assert len(messages) == 2
    assert messages[0].as_bytes() == messages[1].as_bytes()
    assert 'fixture-password' not in artifact.source
