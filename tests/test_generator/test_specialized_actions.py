"""Compile configured app actions without shipping an Action interpreter."""
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.workflow_generator import WorkflowBuilder


def application(tmp_path, action, question_type='NumericUpDown', default='3'):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x', 'other'], [['2', '9'], ['5', '8']])
    target = builder.add_formula([('result', 'Int64', '8', '[x] * 2')])
    builder.connect(source, target)
    root = ET.fromstring(builder.render())
    properties = root.find('Properties')
    old = properties.find('RuntimeProperties')
    if old is not None:
        properties.remove(old)
    runtime = ET.SubElement(properties, 'RuntimeProperties')
    question = ET.SubElement(ET.SubElement(runtime, 'Questions'), 'Question')
    for key, value in [('Type', question_type), ('Name', 'answer'), ('Default', default)]:
        ET.SubElement(question, key).text = value
    actions = ET.SubElement(runtime, 'Actions')
    actions.append(ET.fromstring(action.replace('TARGET', str(target))))
    return XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), tmp_path / 'app.yxwz')


@pytest.mark.parametrize('answer', [1, 4])
def test_specialized_conditional_formula_and_raw_xml(tmp_path, answer):
    action = '''<Condition><Expression>[answer] &gt; 2</Expression><True>
    <Action><Type>UpdateValueFormula</Type><Expression>"[x] + 1"</Expression>
    <Destination>TARGET/FormulaFields/FormulaField/@expression</Destination></Action></True><False>
    <Action><Type>UpdateRawXml</Type><Expression>'&lt;FormulaField field="result" expression="[x] - 1" type="Int64" size="8"/&gt;'</Expression>
    <Destination>TARGET/FormulaFields</Destination></Action></False></Condition>'''
    workflow = application(tmp_path, action)
    artifact = ReadablePythonGenerator().generate(workflow, answers={'answer': answer}, parameter_mode='specialized')
    assert artifact.manifest['parameter_mode'] == 'specialized'
    assert artifact.manifest['bound_answers'] == {'answer': answer}
    assert not artifact.manifest['parameters']
    assert 'UpdateRawXml' not in artifact.source
    namespace = {'__file__': str(tmp_path / 'native.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'output', checkpoints=checkpoints)
    expected = run_workflow_graph(workflow, WorkflowContext(runtime_config={'answers': {'answer': answer}}))
    for node_id, result in expected.node_results.items():
        for anchor, frame in result.outputs.items():
            pd.testing.assert_frame_equal(frame, checkpoints[node_id][anchor])


@pytest.mark.parametrize('answer', [False, True])
def test_specialized_delete_tool_changes_topology(tmp_path, answer):
    workflow = application(tmp_path, '<NoCondition><True><Action><Type>DeleteTool</Type><Variable>answer</Variable>'
        '<Destination>TARGET/FormulaFields</Destination></Action></True></NoCondition>', 'BooleanGroup', 'False')
    artifact = ReadablePythonGenerator().generate(workflow, answers={'answer': answer}, parameter_mode='specialized')
    assert len(artifact.manifest['nodes']) == (1 if answer else 2)
    namespace = {'__file__': str(tmp_path / 'native.py')}
    exec(artifact.source, namespace)
    namespace['run_workflow'](output_dir=tmp_path / 'output')


def test_specialized_question_tokens_without_action(tmp_path):
    workflow = application(tmp_path, '<NoCondition><True/></NoCondition>')
    workflow.source_xml = workflow.source_xml.replace('[x] * 2', '[x] * %Question.answer%')
    workflow = XmlWorkflowParser().parse_xml(workflow.source_xml, tmp_path / 'tokens.yxwz')
    artifact = ReadablePythonGenerator().generate(workflow, answers={'answer': 5}, parameter_mode='specialized')
    namespace = {'__file__': str(tmp_path / 'native.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'output', checkpoints=checkpoints)
    assert checkpoints['2']['Output']['result'].tolist() == [10, 25]


def test_compile_time_variable_override_matches_runtime(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['3']])
    target = builder.add_formula([('result', 'Double', '8', '[x] * [User.rate]')])
    builder.connect(source, target)
    root = ET.fromstring(builder.render())
    constants = ET.SubElement(root.find('Properties'), 'Constants')
    constant = ET.SubElement(constants, 'Constant')
    for key, value in [('Namespace', 'User'), ('Name', 'rate'), ('Value', '2')]:
        ET.SubElement(constant, key).text = value
    ET.SubElement(constant, 'IsNumeric', value='True')
    workflow = XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), tmp_path / 'variables.yxmd')
    artifact = ReadablePythonGenerator().generate(workflow, constants={'User.rate': 4})
    assert artifact.manifest['constant_overrides'] == {'User.rate': 4}
    namespace = {'__file__': str(tmp_path / 'native.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'output', checkpoints=checkpoints)
    assert checkpoints[str(target)]['Output']['result'].tolist() == [12.0]
    with pytest.raises(ValueError, match='Unknown workflow constant'):
        ReadablePythonGenerator().generate(workflow, constants={'User.missing': 4})


def test_specialized_select_list_preserves_field_names_with_commas(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['last, first', 'other'], [['Alice', '9']])
    target = builder.add_select([('last, first', 'True'), ('other', 'True')], include_unknown=False)
    builder.connect(source, target)
    root = ET.fromstring(builder.render())
    runtime = root.find('Properties/RuntimeProperties')
    if runtime is None:
        runtime = ET.SubElement(root.find('Properties'), 'RuntimeProperties')
    for child in list(runtime):
        if child.tag in {'Questions', 'Actions'}:
            runtime.remove(child)
    runtime.append(ET.fromstring('<Questions><Question><Type>ListBox</Type><Name>pick</Name><Default>other</Default></Question></Questions>'))
    runtime.append(ET.fromstring(f'<Actions><NoCondition><True><Action><Type>UpdateSelect</Type><Variable>pick</Variable>'
        f'<Destination>{target}/SelectFields</Destination></Action></True></NoCondition></Actions>'))
    workflow = XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), tmp_path / 'select.yxwz')
    artifact = ReadablePythonGenerator().generate(workflow, answers={'pick': ['last, first']}, parameter_mode='specialized')
    baseline = run_workflow_graph(workflow, WorkflowContext(runtime_config={'answers': {'pick': ['last, first']}}))
    namespace = {'__file__': str(tmp_path / 'native.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'output', checkpoints=checkpoints)
    expected = baseline.node_results[str(target)].outputs['Output']
    assert list(expected.columns) == ['last, first']
    pd.testing.assert_frame_equal(expected, checkpoints[str(target)]['Output'])


def test_update_field_list_changes_only_named_destination():
    from alteryx2python.runtime.app_config import apply_actions
    root = ET.fromstring('''<AlteryxDocument><Nodes><Node ToolID="1"><Properties><Configuration>
        <GroupFields><Field field="group"/></GroupFields><DataFields><Field field="old"/></DataFields>
        </Configuration></Properties></Node></Nodes><Properties><RuntimeProperties><Actions><NoCondition><True>
        <Action><Type>UpdateFieldList</Type><Variable>pick</Variable><Destination>1/DataFields</Destination></Action>
        </True></NoCondition></Actions></RuntimeProperties></Properties></AlteryxDocument>''')
    result = apply_actions(root, {'pick': ['one,two', 'value']})
    assert result.find('.//GroupFields/Field').get('field') == 'group'
    assert [item.get('field') for item in result.findall('.//DataFields/Field')] == ['one,two', 'value']
    assert root.find('.//DataFields/Field').get('field') == 'old'
