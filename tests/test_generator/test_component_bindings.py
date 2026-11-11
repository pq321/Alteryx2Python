import ast
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.workflow_generator import WorkflowBuilder


def app(builder, kind, default, destination, choices=(), action_mode='UpdateValueReplace'):
    root = ET.fromstring(builder.render())
    properties = root.find('Properties')
    previous = properties.find('RuntimeProperties')
    if previous is not None:
        properties.remove(previous)
    runtime = ET.SubElement(properties, 'RuntimeProperties')
    question = ET.SubElement(ET.SubElement(runtime, 'Questions'), 'Question')
    for key, value in [('Type', kind), ('Name', 'answer'), ('ToolId', '90'), ('Default', default)]:
        ET.SubElement(question, key).text = str(value)
    for choice in choices:
        ET.SubElement(question, 'Option').text = choice
    group = ET.SubElement(ET.SubElement(ET.SubElement(runtime, 'Actions'), 'NoCondition'), 'True')
    action = ET.SubElement(group, 'Action')
    for key, value in [('Type', action_mode), ('Variable', 'answer'), ('Destination', destination), ('ReplaceText', '__ANSWER__')]:
        ET.SubElement(action, key).text = value
    return XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), Path('parameter-app.yxwz'))


def compare(workflow, artifact, answers, tmp_path):
    baseline = run_workflow_graph(workflow, WorkflowContext(runtime_config={'answers': answers}))
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](input_dir=tmp_path, output_dir=tmp_path / 'output', checkpoints=checkpoints, **answers)
    for node_id, node in baseline.node_results.items():
        for anchor, expected in node.outputs.items():
            pd.testing.assert_frame_equal(expected, checkpoints[node_id][anchor], check_exact=True)
            assert expected.attrs == checkpoints[node_id][anchor].attrs
    return checkpoints


@pytest.mark.parametrize('kind,default,changed', [
    ('TextBox', 'one', 'different value'),
    ('QuestionTextBox', 'one', 'a different text value'),
    ('Date', '2026-11-12', '2027-02-03'),
    ('DropDown', 'red', 'green'),
    ('NumericUpDown', '2', 9),
    ('RadioButtonGroup', 'True', False),
    ('CheckBoxGroup', 'False', True),
])
def test_packaged_question_action_formula_uses_one_compilation(tmp_path, kind, default, changed):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['1'], ['3']])
    numeric = kind in {'NumericUpDown', 'RadioButtonGroup', 'CheckBoxGroup'}
    formula = builder.add_formula([('answer_value', 'Double' if numeric else 'V_WString', '8' if numeric else '128', '__ANSWER__' if numeric else "'__ANSWER__'")])
    builder.connect(source, formula)
    workflow = app(builder, kind, default, f'{formula}/FormulaFields/FormulaField/@expression', ('red', 'green') if kind == 'DropDown' else ())
    artifact = ReadablePythonGenerator().generate(workflow)
    assert artifact.manifest['parameters'][0]['target_node_ids'] == [str(formula)]
    assert artifact.manifest['parameters'][0]['source_node_id'] == '90'
    assert 'Action' not in [node['tool_type'] for node in artifact.manifest['nodes']]
    compare(workflow, artifact, {'answer': changed}, tmp_path)


@pytest.mark.parametrize('answer', ['17', 'changed text', ''])
def test_text_input_cell_binding_reinfers_types_at_runtime(tmp_path, answer):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['value'], [['__ANSWER__'], ['5']])
    workflow = app(builder, 'TextBox', '2', f'{source}/Data/r[1]/c[1]')
    artifact = ReadablePythonGenerator().generate(workflow)
    compare(workflow, artifact, {'answer': answer}, tmp_path)


def test_file_parameter_preserves_format_and_changes_data(tmp_path):
    builder = WorkflowBuilder()
    source = builder._node('DbFileInput', '<File FileFormat="0">__ANSWER__</File>', (0, 0))
    workflow = app(builder, 'FileBrowse', 'first.csv', f'{source}/File')
    workflow.source_file = str(tmp_path / 'parameter-app.yxwz')
    for node in workflow.nodes:
        node.config['normalized']['base_dir'] = str(tmp_path)
    (tmp_path / 'first.csv').write_text('count\n1\n', encoding='utf-8')
    (tmp_path / 'second.csv').write_text('count\n8\n9\n', encoding='utf-8')
    artifact = ReadablePythonGenerator().generate(workflow)
    compare(workflow, artifact, {'answer': 'second.csv'}, tmp_path)
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.source, namespace)
    with pytest.raises(ValueError, match='format'):
        namespace['run_workflow'](input_dir=tmp_path, output_dir=tmp_path / 'bad', answer='other.xlsx')


def test_native_python_tool_retains_code_and_numbered_outputs(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['2'], ['5']])
    python = builder._node('JupyterCode', '<productionModeScript><![CDATA[from ayx import Alteryx\nframe = Alteryx.read("#1")\nframe["twice"] = frame["x"] * 2\nAlteryx.write(frame, 1)\nAlteryx.write(frame.iloc[:1], 3)]]></productionModeScript>', (1, 0))
    builder.connect(source, python)
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'python.yxmd')
    artifact = ReadablePythonGenerator().generate(workflow)
    assert 'from ayx' not in artifact.source
    assert 'Alteryx.read' not in artifact.source
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'python-output', checkpoints=checkpoints)
    assert checkpoints[str(python)]['Output']['twice'].tolist() == [4, 10]
    assert checkpoints[str(python)]['Output3']['x'].tolist() == [2]
    compile(ast.parse(artifact.source), '<business>', 'exec')


@pytest.mark.parametrize('script', ['Alteryx.read(name)', 'Alteryx.installPackages(["anything"])', 'Alteryx.write(frame, n)', 'from ayx import Package\nPackage.installPackages([])'])
def test_python_tool_rejects_unmapped_api_without_executing(script):
    from alteryx2python.generator.python_tool import lower_python_script
    with pytest.raises(UnsupportedLowering):
        lower_python_script(script, {'Input': 'frame'})
