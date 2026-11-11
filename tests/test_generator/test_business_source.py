import ast

import pandas as pd
import pytest

from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.workflow_generator import WorkflowBuilder


@pytest.mark.parametrize('field,annotation', [('amount', 'pd'), ('units', 'declare_field'), ('weight', 'Path'), ('cost', '')])
def test_compiler_structure_is_independent_of_sample_and_annotations(tmp_path, field, annotation):
    builder = WorkflowBuilder()
    previous = builder.add_text_input([field], [['2'], ['4'], ['7']])
    for index in range(5):
        current = builder.add_formula([(field + str(index), 'Double', '8', f'[{field}] * {index + 1}')])
        builder.connect(previous, current)
        previous = current
    path = tmp_path / 'different.yxmd'
    path.write_text(builder.render(), encoding='utf-8')
    workflow = XmlWorkflowParser().parse(path)
    if annotation:
        workflow.nodes[1].metadata['annotation'] = {'Name': annotation}
    artifact = ReadablePythonGenerator().generate(workflow)
    assert artifact.source == ReadablePythonGenerator().generate(workflow).source
    assert 'checkpoints' not in artifact.source
    assert 'source_tool_id' not in artifact.source
    assert 'node_id' not in artifact.source
    assert '_operation_' not in artifact.source
    assert 'config' not in artifact.source
    assert 'alteryx2python' not in artifact.source
    tree = ast.parse(artifact.source)
    functions = [line for line in tree.body if isinstance(line, ast.FunctionDef)]
    assert functions[0].name == 'run_workflow'
    assert len(functions) < len(workflow.nodes)
    stages = {item['function'] for item in artifact.manifest['nodes']}
    assert len(stages) == 1  # A straight-line chain is one stage, not six wrappers.
    baseline = run_workflow_graph(workflow, WorkflowContext())
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'verification', checkpoints=checkpoints)
    for node_id, result in baseline.node_results.items():
        for anchor, expected in result.outputs.items():
            pd.testing.assert_frame_equal(expected, checkpoints[node_id][anchor], check_exact=True)
            assert expected.attrs == checkpoints[node_id][anchor].attrs
    delivered = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.source, delivered)
    delivered['run_workflow'](output_dir=tmp_path / 'delivery')


def test_csv_workflow_does_not_embed_unselected_io_backends(tmp_path):
    path = tmp_path / 'records.csv'
    path.write_text('count,label\n2,a\n3,b\n', encoding='utf-8')
    builder = WorkflowBuilder()
    builder._node('DbFileInput', '<File FileFormat="0">records.csv</File>', (0, 0))
    workflow_path = tmp_path / 'input.yxmd'
    workflow_path.write_text(builder.render(), encoding='utf-8')
    artifact = ReadablePythonGenerator().generate(XmlWorkflowParser().parse(workflow_path))
    assert 'pd.read_csv' in artifact.source
    for unused in ('read_excel', 'sheet_name', '_dbfileinput_', 'config', 'FileFormat'):
        assert unused not in artifact.source


@pytest.mark.parametrize('expression', ['config.get("fields")', 'inputs["Input"]', 'checkpoints.copy()'])
def test_readability_gate_refuses_runtime_configuration_and_capture_machinery(expression):
    from alteryx2python.generator.business_source import validate_business_source
    from alteryx2python.generator.source_linker import UnsupportedLowering
    with pytest.raises(UnsupportedLowering, match='native template is required'):
        validate_business_source(ast.parse('def business(): return ' + expression))


def test_readability_gate_accepts_decimal_local_context():
    from alteryx2python.generator.business_source import validate_business_source

    source = '''
from decimal import Decimal, localcontext

def business():
    with localcontext() as context:
        context.prec = 60
        return Decimal(1) / Decimal(7)
'''
    tree = ast.parse(source)
    validate_business_source(tree)
    namespace = {}
    exec(compile(tree, '<decimal-template>', 'exec'), namespace)
    assert len(namespace['business']().as_tuple().digits) == 60


@pytest.mark.parametrize('body,call', [
    ('def operation(value):\n    value = value + 1\n    return value', 'operation(original)'),
    ('def operation(value, amount=1):\n    return value + amount', 'operation(original)'),
    ('def operation(value):\n    temporary = 10\n    return value + 1', 'operation(original)'),
])
def test_inlining_preserves_argument_bindings_defaults_and_caller_locals(body, call):
    from alteryx2python.generator.business_source import assemble
    source = body + f'''
def run_workflow(*, checkpoints=None):
    original = 2
    temporary = 50
    result = {call}
    if checkpoints is not None:
        checkpoints['one'] = {{'Output': result}}
    return original, result, temporary
'''
    mapping = [{'node_id': 'one', 'function': 'operation', 'variables': {'Output': 'result'}, 'inputs': {'Input': 'original'}}]
    delivery, verification = assemble(source, mapping)
    for code in (source, delivery, verification):
        namespace = {}
        exec(code, namespace)
        assert namespace['run_workflow']() == (2, 3, 50)


def test_specialization_does_not_rebind_a_shadowed_helper():
    from alteryx2python.generator.source_linker import SourceLinker
    from alteryx2python.tools.appendfields import _frame
    linker = SourceLinker()
    tree = ast.parse('def compiled(_frame): return _frame({}, "Input")').body[0]
    lowered = linker.bind_globals(tree, {'_frame': _frame, '__name__': 'alteryx2python.tools.appendfields'})
    namespace = {}
    exec(linker.render() + '\n' + ast.unparse(ast.fix_missing_locations(lowered)), namespace)
    assert namespace['compiled'](lambda *args: 'local callable') == 'local callable'


@pytest.mark.parametrize('body', [
    'def operation(x):\n    return x',
    'def operation(x):\n    try:\n        raise ValueError()\n    except ValueError as err:\n        result = x\n    return result',
])
def test_inliner_keeps_temporary_and_exception_names_hygienic(body):
    from alteryx2python.generator.business_source import assemble
    source = body + '''
def run_workflow(*, checkpoints=None):
    x = 0
    x_argument = 7
    err = 7
    result = operation(1)
    if checkpoints is not None:
        checkpoints['one'] = {'Output': result}
    return err, result, x_argument
'''
    mapping = [{'node_id': 'one', 'function': 'operation', 'variables': {'Output': 'result'}, 'inputs': {}}]
    delivery, verification = assemble(source, mapping)
    for code in (delivery, verification):
        namespace = {}
        exec(code, namespace)
        assert namespace['run_workflow']() == (7, 1, 7)


@pytest.mark.parametrize('expression', [
    'invoke(callback)',
    '(lambda _frame: _frame({}, "Input"))(callback)',
    '[_frame({}, "Input") for _frame in [callback]][0]',
])
def test_global_helper_linking_respects_nested_python_scopes(expression):
    from alteryx2python.generator.source_linker import SourceLinker
    from alteryx2python.tools import appendfields
    source = f'''def compiled(callback):
    def invoke(_frame):
        return _frame({{}}, 'Input')
    frame = _frame({{'Input': pd.DataFrame({{'value': [2]}})}}, 'Input')
    return frame, {expression}
'''
    linker = SourceLinker()
    lowered = linker.bind_globals(ast.parse(source).body[0], vars(appendfields))
    namespace = {}
    exec(linker.render() + '\n' + ast.unparse(ast.fix_missing_locations(lowered)), namespace)
    frame, value = namespace['compiled'](lambda *args: 'local callable')
    assert frame['value'].tolist() == [2]
    assert value == 'local callable'


def test_manifest_tracks_compile_time_type_defaults(tmp_path, monkeypatch):
    from alteryx2python.tools.field_contracts import DEFAULT_SIZES
    builder = WorkflowBuilder()
    source = builder.add_text_input(['label'], [['long label']])
    formula = builder.add_formula([('copy', 'V_WString', '', '[label]')])
    builder.connect(source, formula)
    path = tmp_path / 'types.yxmd'
    path.write_text(builder.render(), encoding='utf-8')
    workflow = XmlWorkflowParser().parse(path)
    field = workflow.nodes[1].config['normalized']['formula_fields'][0]
    field['size'] = None
    before = ReadablePythonGenerator().generate(workflow)
    monkeypatch.setitem(DEFAULT_SIZES, 'V_WString', 5)
    after = ReadablePythonGenerator().generate(workflow)
    assert before.source != after.source
    assert before.manifest['semantic_constants'] != after.manifest['semantic_constants']
    assert 'tools/field_contracts.py' in after.manifest['semantic_sha256']


@pytest.mark.parametrize('question', ['pd', 'float', 'input_dir', 'checkpoints'])
def test_user_parameters_cannot_shadow_generated_runtime_names(tmp_path, question):
    from xml.etree import ElementTree as ET
    builder = WorkflowBuilder()
    source = builder.add_text_input(['amount'], [['2'], ['4'], ['7']])
    target = builder.add_filter('[amount] >= ANSWER')
    builder.connect(source, target)
    root = ET.fromstring(builder.render())
    runtime = root.find('Properties/RuntimeProperties')
    if runtime is None:
        runtime = ET.SubElement(root.find('Properties'), 'RuntimeProperties')
    for item in list(runtime):
        if item.tag in {'ModuleType', 'Questions', 'Actions'}:
            runtime.remove(item)
    ET.SubElement(runtime, 'ModuleType').text = 'Wizard'
    runtime.append(ET.fromstring(f'<Questions><Question><Type>NumericUpDown</Type><Name>{question}</Name><Default>3</Default></Question></Questions>'))
    runtime.append(ET.fromstring(f'<Actions><NoCondition><True><Action><Type>UpdateValue</Type><Variable>{question}</Variable><Replace value="True"/><ReplaceText>ANSWER</ReplaceText><Destination>{target}/Expression</Destination></Action></True></NoCondition></Actions>'))
    path = tmp_path / 'named-input.yxwz'
    path.write_text(ET.tostring(root, encoding='unicode'), encoding='utf-8')
    artifact = ReadablePythonGenerator().generate(XmlWorkflowParser().parse(path))
    name = artifact.manifest['parameters'][0]['python_name']
    assert name != question
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'verification', checkpoints=checkpoints, **{name: 5})
    assert checkpoints[str(target)]['True']['amount'].tolist() == [7]
    delivered = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.source, delivered)
    delivered['run_workflow'](output_dir=tmp_path / 'delivery', **{name: 5})
