import os
import shlex
import subprocess
import sys
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.tools.delivery import command_arguments, run_checked_command
from alteryx2python.workflow_events import workflow_events
from alteryx2python.workflow_generator import WorkflowBuilder


def event_workflow(tmp_path, expression='[value] * 2', size='4'):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['value'], [['12345']])
    target = builder.add_formula([('result','Int32','4',expression), ('short','V_WString',size,'ToString([value])')])
    builder.connect(source,target)
    root = ET.fromstring(builder.render())
    properties = root.find('Properties')
    old = properties.find('Events')
    if old is not None:
        properties.remove(old)
    events = ET.SubElement(properties,'Events')
    ET.SubElement(events,'Enabled',value='True')
    for timing,label in [('Before','before'),('AfterNoErrors','success'),('AfterErrors','failure'),
                         ('AfterWarnings','warnings'),('AfterErrorsWarnings','errors_or_warnings'),
                         ('AfterNoErrorsNoWarnings','clean'),('After','after')]:
        event = ET.SubElement(events,'Event')
        ET.SubElement(event,'When').text = timing
        ET.SubElement(event,'cmd_Program').text = sys.executable
        code = 'from pathlib import Path; p=Path("events.txt"); p.write_text((p.read_text() if p.exists() else "")+' + repr(label+'\n') + ')'
        args = ['-c',code]
        ET.SubElement(event,'cmd_CommandLine').text = subprocess.list2cmdline(args) if os.name == 'nt' else shlex.join(args)
        ET.SubElement(event,'cmd_WorkingDir').text = 'configured'
    path = tmp_path / 'events.yxmd'
    path.write_text(ET.tostring(root,encoding='unicode'),encoding='utf-8')
    return XmlWorkflowParser().parse(path)


@pytest.mark.parametrize('outcome', ['clean','warnings','failure'])
def test_before_after_success_failure_and_warning_events(tmp_path,outcome):
    workflow = event_workflow(tmp_path, '[value] / 0' if outcome == 'failure' else '[value] * 2',
                              '2' if outcome == 'warnings' else '20')
    expected_root, actual_root = tmp_path/'baseline',tmp_path/'readable'
    context = WorkflowContext(runtime_config={'input_dir':str(expected_root), 'output_dir':str(tmp_path/'unrelated'),
        'allowed_commands':[sys.executable]})
    artifact = ReadablePythonGenerator().generate(workflow)
    namespace = {'__file__':str(tmp_path/'readable.py')}
    exec(artifact.source,namespace)
    def baseline():
        return run_workflow_graph(workflow,context)
    def readable():
        return namespace['run_workflow'](input_dir=actual_root, output_dir=tmp_path/'output', allowed_commands=[sys.executable])
    for run in (baseline,readable):
        if outcome == 'failure':
            with pytest.raises(ZeroDivisionError):
                run()
        else:
            run()
    expected = {'clean':['before','success','clean','after'],
                'warnings':['before','success','warnings','errors_or_warnings','after'],
                'failure':['before','failure','errors_or_warnings','after']}[outcome]
    assert (expected_root/'configured/events.txt').read_text().splitlines() == expected
    assert (actual_root/'configured/events.txt').read_text().splitlines() == expected
    assert not (tmp_path/'unrelated/events.txt').exists()


def test_disabled_and_unknown_events_fail_explicitly():
    assert workflow_events('<AlteryxDocument><Properties><Events><Enabled value="False"/><Event><When>unknown</When></Event></Events></Properties></AlteryxDocument>') == []
    with pytest.raises(NotImplementedError,match='Unknown enabled'):
        workflow_events('<AlteryxDocument><Properties><Events><Event><When>unknown</When></Event></Events></Properties></AlteryxDocument>')


def test_command_arguments_preserve_quoted_paths_and_backslashes(tmp_path):
    args = ['C:\\some folder\\file.csv','quoted "value"','', 'trailing\\']
    encoded = subprocess.list2cmdline(args) if os.name == 'nt' else shlex.join(args)
    assert command_arguments(encoded) == args
    with pytest.raises(PermissionError,match='explicitly allowed'):
        run_checked_command(sys.executable,['-c','pass'],tmp_path,None,'','',[])


@pytest.mark.skipif(os.name != 'nt',reason='Windows batch execution')
def test_batch_path_with_spaces(tmp_path):
    script = tmp_path/'command with spaces.cmd'
    script.write_text('@echo off\r\necho %~1>result.txt\r\n',encoding='ascii')
    run_checked_command(str(script),['argument with spaces'],tmp_path,None,'','',[str(script)])
    assert (tmp_path/'result.txt').read_text().strip() == 'argument with spaces'
