from copy import deepcopy
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.runtime.variables import ACTIVE_VARIABLES
from alteryx2python.workflow_generator import WorkflowBuilder


def with_constants(xml, declarations):
    root = ET.fromstring(xml)
    properties = root.find('Properties')
    if properties is None:
        properties = ET.SubElement(root, 'Properties')
    constants = ET.SubElement(properties, 'Constants')
    for namespace, name, value, numeric in declarations:
        constant = ET.SubElement(constants, 'Constant')
        for key, item in [('Namespace', namespace), ('Name', name), ('Value', str(value))]:
            ET.SubElement(constant, key).text = item
        ET.SubElement(constant, 'IsNumeric', value=str(numeric))
    return ET.tostring(root, encoding='unicode')


def test_user_global_engine_and_percent_constants_match_native_python(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['2'], ['5']])
    formula = builder.add_formula([('amount', 'Double', '8', '[x] * [User.rate]'),
                                   ('label', 'V_WString', '64', '[%Global.label%]'),
                                   ('workflow', 'V_WString', '255', '[Engine.WorkflowFileName]')])
    builder.connect(source, formula)
    xml = with_constants(builder.render(), [('User', 'rate', 1.25, True), ('Global', 'label', 'tax report', False)])
    workflow = XmlWorkflowParser().parse_xml(xml, tmp_path / 'constants.yxmd')
    before = deepcopy(workflow)
    context = WorkflowContext(runtime_config={'mode': 'test'})
    baseline = run_workflow_graph(workflow, context)
    assert workflow == before
    assert context.runtime_config == {'mode': 'test'}
    assert ACTIVE_VARIABLES.get() == {}
    expected = baseline.node_results[str(formula)].outputs['Output']
    assert expected['amount'].tolist() == [2.5, 6.25]
    assert expected['label'].tolist() == ['tax report', 'tax report']
    assert expected['workflow'].tolist() == ['constants.yxmd', 'constants.yxmd']
    artifact = ReadablePythonGenerator().generate(workflow)
    assert 'USER_RATE_' in artifact.source and 'GLOBAL_LABEL_' in artifact.source
    namespace = {'__file__': str(tmp_path / 'native.py')}
    exec(artifact.verification_source, namespace)
    captured = {}
    namespace['run_workflow'](output_dir=tmp_path / 'result', checkpoints=captured)
    pd.testing.assert_frame_equal(expected, captured[str(formula)]['Output'], check_exact=True)


def test_explicit_user_override_does_not_leak_to_later_runs(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['3']])
    target = builder.add_formula([('answer', 'Double', '8', '[x] * [User.rate]')])
    builder.connect(source, target)
    workflow = XmlWorkflowParser().parse_xml(with_constants(builder.render(), [('User', 'rate', 2, True)]), tmp_path / 'variables.yxmd')
    for overrides, expected in [({'User.rate': 4}, 12), ({}, 6)]:
        result = run_workflow_graph(workflow, WorkflowContext(runtime_config={'constants': overrides}))
        assert result.node_results[str(target)].outputs['Output']['answer'].tolist() == [expected]
    with pytest.raises(ValueError, match='Unknown workflow constant'):
        run_workflow_graph(workflow, WorkflowContext(runtime_config={'constants': {'User.typo': 3}}))


def test_saved_python_can_read_workflow_user_constant(tmp_path):
    builder = WorkflowBuilder()
    python = builder._node('JupyterCode', '<productionModeScript><![CDATA[from ayx import Alteryx\nimport pandas as pd\nAlteryx.write(pd.DataFrame({"rate": [Alteryx.getWorkflowConstant("User.rate")]}), 2)]]></productionModeScript>', (0, 0))
    workflow = XmlWorkflowParser().parse_xml(with_constants(builder.render(), [('User', 'rate', 7, True)]), tmp_path / 'python.yxmd')
    baseline = run_workflow_graph(workflow, WorkflowContext())
    assert baseline.node_results[str(python)].outputs['Output2']['rate'].tolist() == [7]
    artifact = ReadablePythonGenerator().generate(workflow)
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'result', checkpoints=checkpoints)
    assert checkpoints[str(python)]['Output2']['rate'].tolist() == [7]


def test_wait_seconds_executes_delay_and_preserves_frame(tmp_path, monkeypatch):
    from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR
    import time
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'], [['4']])
    workflow = XmlWorkflowParser().parse_xml(builder.render(), tmp_path / 'wait.yxmd')
    workflow.nodes.append(NodeIR('wait', 'wait', 'WaitASecond', 'wait', {'seconds': 0.125}, output_anchors=[AnchorIR('Output', 'output')]))
    workflow.edges.append(EdgeIR('wait-edge', str(source), 'Output', 'wait', 'Input'))
    workflow.source_xml = ''
    durations = []
    monkeypatch.setattr(time, 'sleep', durations.append)
    baseline = run_workflow_graph(workflow, WorkflowContext())
    artifact = ReadablePythonGenerator().generate(workflow)
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'result', checkpoints=checkpoints)
    assert durations == [0.125, 0.125]
    pd.testing.assert_frame_equal(baseline.node_results['wait'].outputs['Output'], checkpoints['wait']['Output'])


@pytest.mark.parametrize('duration', [-1, float('inf'), float('nan')])
def test_invalid_wait_never_sleeps(duration, monkeypatch):
    from alteryx2python.tools.wait import wait_seconds_tool
    import time
    monkeypatch.setattr(time, 'sleep', lambda value: pytest.fail('Invalid delay executed'))
    with pytest.raises(ValueError, match='duration'):
        wait_seconds_tool({'Input': pd.DataFrame()}, {'seconds': duration}, WorkflowContext())


def test_nested_macro_constants_are_local_and_engine_references_remain_expressions(tmp_path):
    from alteryx2python.generator.python_generator import PythonGenerator
    from alteryx2python.generator.readable import read_phase_one

    inner = WorkflowBuilder()
    source = inner._node('MacroInput', '<Name>Input</Name>', (0, 0))
    formula = inner.add_formula([('inner_value', 'Double', '8', '[x] * [User.rate]'),
                                 ('inner_file', 'V_WString', '255', '[%Engine.WorkflowFileName%]')])
    sink = inner._node('MacroOutput', '<Name>Output</Name>', (2, 0))
    inner.connect(source, formula)
    inner.connect(formula, sink)
    inner_path = tmp_path / 'Inner.yxmc'
    inner_path.write_text(with_constants(inner.render(), [('User', 'rate', 3, True)]), encoding='utf-8')

    wrapper = WorkflowBuilder()
    source = wrapper._node('MacroInput', '<Name>Input</Name>', (0, 0))
    caller = wrapper._tool_id()
    wrapper.nodes_xml.append(f'<Node ToolID="{caller}"><GuiSettings/><Properties><Configuration/></Properties><EngineSettings Macro="Inner.yxmc"/></Node>')
    formula = wrapper.add_formula([('wrapper_value', 'Double', '8', '[x] * [User.rate]')])
    sink = wrapper._node('MacroOutput', '<Name>Output</Name>', (3, 0))
    wrapper.connect(source, caller)
    wrapper.connect(caller, formula)
    wrapper.connect(formula, sink)
    wrapper_path = tmp_path / 'Wrapper.yxmc'
    wrapper_path.write_text(with_constants(wrapper.render(), [('User', 'rate', 5, True)]), encoding='utf-8')

    outer = WorkflowBuilder()
    source = outer.add_text_input(['x'], [['2']])
    caller = outer._tool_id()
    outer.nodes_xml.append(f'<Node ToolID="{caller}"><GuiSettings/><Properties><Configuration/></Properties><EngineSettings Macro="Wrapper.yxmc"/></Node>')
    outer.connect(source, caller)
    workflow = XmlWorkflowParser().parse_xml(with_constants(outer.render(), [('User', 'rate', 11, True)]), tmp_path / 'outer.yxmd')
    phase_one = tmp_path / 'phase_one.py'
    phase_one.write_text(PythonGenerator().generate(workflow), encoding='utf-8')
    inner_path.unlink()
    wrapper_path.unlink()
    preserved = read_phase_one(phase_one)
    baseline = run_workflow_graph(preserved, WorkflowContext(runtime_config={'constants': {'User.rate': 17}}))
    expected = baseline.node_results[str(caller)].outputs['Output']
    assert expected['inner_value'].tolist() == [6]
    assert expected['wrapper_value'].tolist() == [10]
    assert expected['inner_file'].tolist() == ['Inner.yxmc']
    artifact = ReadablePythonGenerator().generate(preserved)
    namespace = {'__file__': str(tmp_path / 'business.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'output', checkpoints=checkpoints)
    pd.testing.assert_frame_equal(expected, checkpoints[str(caller)]['Output'], check_exact=True)
    assert ACTIVE_VARIABLES.get() == {}


def test_record_field_precedence_over_unwrapped_constant_is_preserved(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['User.rate'], [['7']])
    formula = builder.add_formula([('answer', 'Int32', '4', '[User.rate]')])
    builder.connect(source, formula)
    workflow = XmlWorkflowParser().parse_xml(with_constants(builder.render(), [('User', 'rate', 3, True)]), tmp_path / 'precedence.yxmd')
    expected = run_workflow_graph(workflow, WorkflowContext()).node_results[str(formula)].outputs['Output']
    artifact = ReadablePythonGenerator().generate(workflow)
    namespace = {'__file__': str(tmp_path / 'native.py')}
    exec(artifact.verification_source, namespace)
    captured = {}
    namespace['run_workflow'](output_dir=tmp_path / 'out', checkpoints=captured)
    assert expected['answer'].tolist() == [7]
    pd.testing.assert_frame_equal(expected, captured[str(formula)]['Output'])
