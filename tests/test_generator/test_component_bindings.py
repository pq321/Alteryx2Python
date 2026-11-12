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


def test_dynamic_question_values_reach_command_events(tmp_path):
    import os
    import shlex
    import subprocess
    import sys
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['2']])
    target = builder.add_formula([('result', 'Int64', '8', '[x] * __ANSWER__')])
    builder.connect(source, target)
    workflow = app(builder, 'NumericUpDown', '2', f'{target}/FormulaFields/FormulaField/@expression')
    root = ET.fromstring(workflow.source_xml)
    event = ET.SubElement(ET.SubElement(root.find('Properties'), 'Events'), 'Event')
    ET.SubElement(event, 'When').text = 'AfterNoError'
    ET.SubElement(event, 'cmd_Program').text = sys.executable
    args = ['-c', 'from pathlib import Path; Path("event.txt").write_text("%Question.answer%")']
    ET.SubElement(event, 'cmd_CommandArguments').text = subprocess.list2cmdline(args) if os.name == 'nt' else shlex.join(args)
    workflow = XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), tmp_path / 'events.yxwz')
    artifact = ReadablePythonGenerator().generate(workflow)
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.source, namespace)
    native_dir = tmp_path / 'native'
    native_dir.mkdir()
    namespace['run_workflow'](input_dir=native_dir, output_dir=native_dir, allowed_commands=[sys.executable], answer=7)
    assert (native_dir / 'event.txt').read_text() == '7'
    baseline_dir = tmp_path / 'canonical'
    baseline_dir.mkdir()
    run_workflow_graph(workflow, WorkflowContext(runtime_config={'input_dir': str(baseline_dir),
        'allowed_commands': [sys.executable], 'answers': {'answer': 7}}))
    assert (baseline_dir / 'event.txt').read_text() == '7'


@pytest.mark.parametrize('reference', ['[Question.answer]', '[%Question.answer%]', '%Question.answer%'])
def test_dynamic_question_references_without_actions(tmp_path, reference):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['3']])
    target = builder.add_formula([('result', 'Int64', '8', f'[x] * {reference}')])
    builder.connect(source, target)
    root = ET.fromstring(builder.render())
    runtime = root.find('Properties/RuntimeProperties')
    runtime[:] = []
    runtime.append(ET.fromstring('<Questions><Question><Type>NumericUpDown</Type><Name>answer</Name><Default>2</Default></Question></Questions>'))
    workflow = XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), tmp_path / 'question.yxwz')
    artifact = ReadablePythonGenerator().generate(workflow)
    checkpoints = compare(workflow, artifact, {'answer': 7}, tmp_path)
    assert checkpoints[str(target)]['Output']['result'].tolist() == [21]


@pytest.mark.parametrize('name', ['User.rate', 'Global.rate', 'Engine.rate', 'Question.rate'])
def test_namespaced_record_fields_are_not_missing_constants(tmp_path, name):
    builder = WorkflowBuilder()
    source = builder.add_text_input([name], [['4']])
    target = builder.add_formula([('result', 'Int64', '8', f'[{name}] * 2')])
    builder.connect(source, target)
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'fields.yxmd')
    artifact = ReadablePythonGenerator().generate(workflow)
    checkpoints = compare(workflow, artifact, {}, tmp_path)
    assert checkpoints[str(target)]['Output']['result'].tolist() == [8]


def test_dynamic_output_filename_and_mail_attachment_share_binding(tmp_path):
    from email import policy
    from email.parser import BytesParser
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['3']])
    sink = builder.add_csv_output('report.csv')
    builder.connect(source, sink)
    workflow = app(builder, 'FileBrowse', 'report.csv', f'{sink}/File', action_mode='UpdateOutput')
    root = ET.fromstring(workflow.source_xml)
    ET.SubElement(root.find('.//Action'), 'OutputTool').text = str(sink)
    event = ET.SubElement(ET.SubElement(root.find('Properties'), 'Events'), 'Event')
    for key, value in [('When', 'AfterNoError'), ('SendMail', 'True'), ('email_From', 'from@example.invalid'),
                       ('email_To', 'to@example.invalid'), ('email_Subject', 'Report'), ('email_Body', 'Attached')]:
        ET.SubElement(event, key).text = value
    ET.SubElement(ET.SubElement(event, 'email_Attachments'), 'attachment').text = '%Question.answer%'
    workflow = XmlWorkflowParser().parse_xml(ET.tostring(root, encoding='unicode'), tmp_path / 'mail.yxwz')
    artifact = ReadablePythonGenerator().generate(workflow, delivery_profile='html-draft-v1')
    namespace = {'__file__': str(tmp_path / 'native.py')}
    exec(artifact.source, namespace)
    output = tmp_path / 'native'
    namespace['run_workflow'](input_dir=tmp_path, output_dir=output, answer='changed.csv')
    message = BytesParser(policy=policy.default).parsebytes((output / 'event-0.eml').read_bytes())
    attachment = next(message.iter_attachments())
    assert attachment.get_filename() == 'changed.csv'
    assert attachment.get_payload(decode=True) == (output / 'changed.csv').read_bytes()


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


@pytest.mark.parametrize('kind', ['ToolContainer', 'ControlContainer'])
@pytest.mark.parametrize('disabled', [False, True])
def test_packaged_boolean_action_controls_nested_container(tmp_path, kind, disabled):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['4']])
    formula = builder.add_formula([('answer_value', 'Int32', '4', '[x] * 3')])
    container = builder._tool_id()
    builder.nodes_xml.append(f'<Node ToolID="{container}"><GuiSettings Plugin="AlteryxGuiToolkit.{kind}.{kind}"/><Properties><Configuration><Disabled value="True"/></Configuration></Properties></Node>')
    builder.connect(source, formula)
    workflow = app(builder, 'RadioButtonGroup', 'True', f'{container}/Disabled/@value', action_mode='UpdateValue')
    by_id = {node.node_id: node for node in workflow.nodes}
    by_id[str(formula)].config['container_id'] = str(container)
    by_id[str(container)].config['child_node_ids'] = [str(formula)]
    artifact = ReadablePythonGenerator().generate(workflow)
    checkpoints = compare(workflow, artifact, {'answer': disabled}, tmp_path)
    assert len(checkpoints[str(formula)]['Output']) == (0 if disabled else 1)


@pytest.mark.parametrize('text', ["can't", 'say "hi"', 'path\\name', 'line\nbreak'])
def test_raw_expression_actions_reject_ambiguous_escaping(tmp_path, text):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['1']])
    formula = builder.add_formula([('value', 'V_WString', '128', "'__ANSWER__'")])
    builder.connect(source, formula)
    workflow = app(builder, 'TextBox', 'safe', f'{formula}/FormulaFields/FormulaField/@expression')
    artifact = ReadablePythonGenerator().generate(workflow)
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.source, namespace)
    with pytest.raises(ValueError, match='quoting or escapes'):
        namespace['run_workflow'](output_dir=tmp_path / 'out', answer=text)


def test_python_user_names_and_nested_signatures_survive_delivery(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['2'], ['5']])
    script = '''from ayx import Alteryx
input_frame = None
_input_0 = None
config = {"multiplier": 3}
inputs = Alteryx.read("#1")
def calculate(checkpoints):
    return checkpoints * config["multiplier"]
inputs["result"] = calculate(checkpoints=inputs["x"])
Alteryx.write(inputs, 1)'''
    python = builder._node('JupyterCode', '<productionModeScript><![CDATA[' + script + ']]></productionModeScript>', (1, 0))
    builder.connect(source, python)
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'python.yxmd')
    artifact = ReadablePythonGenerator().generate(workflow)
    compare(workflow, artifact, {}, tmp_path)
    namespace = {'__file__': str(tmp_path / 'delivered.py')}
    exec(artifact.source, namespace)
    # The shipped build must retain the user's checkpoints keyword/signature.
    namespace['run_workflow'](output_dir=tmp_path / 'delivered')


def test_python_metadata_output_applies_names_types_and_widths(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x', 'label'], [['2', 'abcdef'], ['5', 'xyz']])
    script = '''from ayx import Alteryx
frame = Alteryx.read("#1")
metadata = Alteryx.readMetadata("#1")
assert metadata["x"]["type"] == "Int64"
metadata["label"] = {"name": "short_label", "type": "V_WString", "length": (3,)}
metadata["x"] = {"name": "small_number", "type": "Int16"}
Alteryx.write(frame, 2, columns=metadata)'''
    python = builder._node('JupyterCode', '<productionModeScript><![CDATA[' + script + ']]></productionModeScript>', (1, 0))
    builder.connect(source, python)
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'metadata.yxmd')
    artifact = ReadablePythonGenerator().generate(workflow)
    with pytest.warns(RuntimeWarning, match='truncated'):
        captured = compare(workflow, artifact, {}, tmp_path)
    frame = captured[str(python)]['Output2']
    assert frame['short_label'].tolist() == ['abc', 'xyz']
    assert str(frame['small_number'].dtype) == 'Int16'
    assert frame.attrs['alteryx_schema'] == [
        {'name': 'small_number', 'type': 'Int16', 'size': 2},
        {'name': 'short_label', 'type': 'V_WString', 'size': 3},
    ]


@pytest.mark.parametrize('override_source', [False, True])
def test_python_type_override_preserves_unmodified_field_metadata(tmp_path, override_source):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['2'], ['5']])
    metadata = {'type': 'Int16'}
    if override_source:
        metadata['source'] = 'Python output'
    script = '''from ayx import Alteryx
frame = Alteryx.read("#1")
frame.attrs["alteryx_schema"] = [{"name": "x", "type": "Int64", "size": 8,
    "source": "Original input", "description": "Business identifier"}]
Alteryx.write(frame, 1, columns={"x": ''' + repr(metadata) + '''})'''
    python = builder._node('JupyterCode', '<productionModeScript><![CDATA[' + script + ']]></productionModeScript>', (1, 0))
    builder.connect(source, python)
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'metadata-inheritance.yxmd')
    artifact = ReadablePythonGenerator().generate(workflow)
    captured = compare(workflow, artifact, {}, tmp_path)
    assert captured[str(python)]['Output'].attrs['alteryx_schema'] == [{
        'name': 'x', 'type': 'Int16', 'size': 2,
        'source': 'Python output' if override_source else 'Original input',
        'description': 'Business identifier',
    }]


def test_installed_official_python_tool_sample_runs_both_phases(tmp_path):
    sample = Path('D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/22 Developer/Python.yxmd')
    if not sample.is_file():
        pytest.skip('Installed official sample is unavailable')
    workflow = XmlWorkflowParser().parse(sample)
    artifact = ReadablePythonGenerator().generate(workflow)
    compare(workflow, artifact, {}, tmp_path)
    namespace = {'__file__': str(tmp_path / 'delivery.py')}
    exec(artifact.source, namespace)
    namespace['run_workflow'](output_dir=tmp_path / 'delivered')


@pytest.mark.parametrize('method,settings', [
    ('EqualRecords', '<EqualRecords><NumTiles value="2"/></EqualRecords>'),
    ('EqualSum', '<EqualSum><SumField>x</SumField><NumTiles value="2"/></EqualSum>'),
    ('Manual', '<Manual><Field>x</Field><Cutoffs>3\n7</Cutoffs></Manual>'),
])
def test_static_tile_helper_configuration_is_compiled_away(tmp_path, method, settings):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['2'], ['4'], ['6'], ['8']])
    target = builder._node('Tile', '<Method>' + method + '</Method>' + settings, (1, 0))
    builder.connect(source, target)
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'tile.yxmd')
    artifact = ReadablePythonGenerator().generate(workflow)
    compare(workflow, artifact, {}, tmp_path)
    assert not any(isinstance(item, ast.Name) and item.id == 'config' for item in ast.walk(ast.parse(artifact.source)))


@pytest.mark.parametrize('mode', ['Replace', 'Append'])
def test_findreplace_helper_configuration_and_anchor_maps_are_compiled_away(tmp_path, mode):
    builder = WorkflowBuilder()
    target = builder.add_text_input(['label'], [['hello red'], ['green']])
    lookup = builder.add_text_input(['term', 'replacement'], [['red', 'blue']])
    operation = builder._node('FindReplace', '<FieldFind>label</FieldFind><FieldSearch>term</FieldSearch><ReplaceFoundField>replacement</ReplaceFoundField><ReplaceMode>' + mode + '</ReplaceMode><ReplaceAppendFields><Field field="replacement"/></ReplaceAppendFields>', (1, 0))
    builder.connect(target, operation, target_anchor='Targets')
    builder.connect(lookup, operation, target_anchor='Source')
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'replace.yxmd')
    artifact = ReadablePythonGenerator().generate(workflow)
    compare(workflow, artifact, {}, tmp_path)


def _mutating_configuration(config):
    config['value'] = 7
    return config['value']


def _aliased_configuration(config):
    alias = config
    alias['value'] = 7
    return config['value']


@pytest.mark.parametrize('helper', [_mutating_configuration, _aliased_configuration])
def test_helper_configuration_mutation_is_never_frozen(helper, monkeypatch):
    from alteryx2python.generator.source_linker import SourceLinker
    monkeypatch.setattr(helper, '__module__', 'alteryx2python.tools.local_macros')
    with pytest.raises(UnsupportedLowering, match='escapes read-only'):
        SourceLinker().function(helper, {'config': {'value': 2}})


@pytest.mark.parametrize('kind,fields,rows,settings,anchor', [
    ('CreatePoints', ['x', 'y'], [['2', '3'], ['4', '5']], {'x_field': 'x', 'y_field': 'y', 'mode': 'Double'}, 'Input'),
    ('SpatialInfo', ['SpatialObj'], [['POLYGON ((0 0, 4 0, 4 2, 0 2, 0 0))']],
     {'spatial_field': 'SpatialObj', 'selected_items': ['AreaMi', 'CentroidObj', 'CentroidXY']}, 'Input'),
    ('Buffer', ['SpatialObj'], [['POLYGON ((0 1, 1 1, 1 0, 0 0, 0 1))']],
     {'spatial_field': 'SpatialObj', 'include_source': True, 'buffer_size_source': 'SpecificValue', 'buffer_size': '69', 'units': 'Miles'}, 'Input'),
    ('DataCleansing', ['label'], [['  first  '], [' second ']],
     {'selected_fields': ['label'], 'remove_leading_trailing_whitespace': True, 'modify_case': True, 'case_mode': 'upper'}, 'Input2'),
])
def test_audited_input_helpers_keep_local_algorithm_results(tmp_path, kind, fields, rows, settings, anchor):
    builder = WorkflowBuilder()
    source = builder.add_text_input(fields, rows)
    if kind == 'DataCleansing':
        target = builder._tool_id()
        builder.nodes_xml.append(f'<Node ToolID="{target}"><GuiSettings/><Properties><Configuration/></Properties><EngineSettings Macro="Cleanse.yxmc"/></Node>')
    else:
        target = builder._node(kind, '', (1, 0))
    builder.connect(source, target, target_anchor=anchor)
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'local.yxmd')
    next(node for node in workflow.nodes if node.node_id == str(target)).config['normalized'] = settings
    artifact = ReadablePythonGenerator().generate(workflow)
    compare(workflow, artifact, {}, tmp_path)


def test_ordered_joinmultiple_inputs_compile_to_positional_frames(tmp_path):
    builder = WorkflowBuilder()
    first = builder.add_text_input(['key', 'a'], [['first', '1'], ['second', '2']])
    second = builder.add_text_input(['key', 'b'], [['first', '3']])
    target = builder._node('JoinMultiple', '', (1, 0))
    builder.connect(first, target)
    builder.connect(second, target, target_anchor='Input_2')
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'join.yxmd')
    next(node for node in workflow.nodes if node.node_id == str(target)).config['normalized'] = {
        'joins': [{'connection': '#1', 'fields': ['key']}, {'connection': '#2', 'fields': ['key']}]}
    compare(workflow, ReadablePythonGenerator().generate(workflow), {}, tmp_path)
