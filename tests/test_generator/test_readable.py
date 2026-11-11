from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd
import pytest

from alteryx2python.benchmark import build_benchmark, run_benchmark
from alteryx2python.cli import main
from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.generator.readable import ReadablePythonGenerator, UnsupportedLowering, read_phase_one
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.workflow_generator import WorkflowBuilder


DATA = Path(__file__).resolve().parents[2] / 'examples/readable_benchmark/data/iris.data'


def parse(builder, tmp_path):
    path = tmp_path / 'workflow.yxmd'
    path.write_text(builder.render(), encoding='utf-8')
    return XmlWorkflowParser().parse(path)


def run_readable(workflow, tmp_path):
    artifact = ReadablePythonGenerator().generate(workflow)
    namespace = {'__file__': str(tmp_path / 'readable.py')}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace['run_workflow'](output_dir=tmp_path / 'output', checkpoints=checkpoints)
    return artifact, checkpoints


def test_deterministic_source_and_recognized_phase_one(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['value'], [['12'], ['3']])
    target = builder.add_formula([('twice', 'Int32', '4', '[value] * 2')])
    builder.connect(source, target)
    workflow = parse(builder, tmp_path)
    path = tmp_path / 'phase_one.py'
    path.write_text(PythonGenerator().generate(workflow), encoding='utf-8')
    preserved = read_phase_one(path)
    assert asdict(preserved)['nodes'] == asdict(workflow)['nodes']
    generator = ReadablePythonGenerator()
    first, second = generator.generate(preserved), generator.generate(preserved)
    assert first.source == second.source
    assert first.manifest == second.manifest
    assert first.manifest['native_equivalence'] == 'unverified'
    assert 'alteryx2python' not in first.source
    assert 'eval(' not in first.source
    assert 'NODE_DATA' not in first.source
    assert 'parse_expression' not in first.source
    assert 'twice' in first.source and '* 2' in first.source
    paths = first.write(tmp_path / 'editable.py')
    assert len(paths) == 3
    assert json.loads(paths[1].read_text())['generated_sha256'] == hashlib.sha256(first.source.encode()).hexdigest()
    with pytest.raises(FileExistsError):
        first.write(tmp_path / 'editable.py')


@pytest.mark.parametrize('change', ['print("manual behavior")\n', '\ndef hidden():\n    return 1\n'])
def test_phase_one_manual_changes_are_rejected_without_execution(tmp_path, change):
    builder = WorkflowBuilder()
    builder.add_text_input(['value'], [['1']])
    workflow = parse(builder, tmp_path)
    path = tmp_path / 'modified.py'
    path.write_text(PythonGenerator().generate(workflow) + '\n' + change, encoding='utf-8')
    with pytest.raises(UnsupportedLowering, match='manual behavioral edits'):
        read_phase_one(path)


def test_unknown_node_blocks_compilation(tmp_path):
    builder = WorkflowBuilder()
    builder.add_text_input(['value'], [['1']])
    workflow = parse(builder, tmp_path)
    workflow.nodes[0].tool_type = 'UnimplementedForTest'
    with pytest.raises(UnsupportedLowering, match='UnimplementedForTest'):
        ReadablePythonGenerator().generate(workflow)


@pytest.mark.parametrize('kind', ['GenerateRows', 'MultiFieldFormula', 'MultiRowFormula', 'MakeGroup'])
def test_expression_and_group_templates_match_runtime(tmp_path, kind):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['a', 'b'], [['1', '2'], ['2', '3'], ['5', '6']])
    if kind == 'GenerateRows':
        target = builder._node(kind, '<UpdateField value="False"/><CreateField_Name>replicate</CreateField_Name><Expression_Init>1</Expression_Init><Expression_Cond>[replicate]&lt;3</Expression_Cond><Expression_Loop>[replicate]+1</Expression_Loop>', (100,100))
    elif kind == 'MultiFieldFormula':
        target = builder._node(kind, '<Fields><Field name="a"/><Field name="b"/></Fields><CopyOutput value="True"/><NewFieldAddOn>_twice</NewFieldAddOn><Expression>[_CurrentField_]*2</Expression>', (100,100))
    elif kind == 'MultiRowFormula':
        target = builder.add_multi_row_formula('[a] - [Row-1:a]', 'delta')
    else:
        target = builder._node(kind, '<Key1st>a</Key1st><Key2nd>b</Key2nd>', (100,100))
    builder.connect(source, target)
    workflow = parse(builder, tmp_path)
    if kind == 'MakeGroup':
        next(n for n in workflow.nodes if n.node_id == str(target)).config['normalized'] = {'key_first':'a', 'key_second':'b'}
    expected = run_workflow_graph(workflow, WorkflowContext())
    artifact, actual = run_readable(workflow, tmp_path)
    for node_id, node in expected.node_results.items():
        for anchor, frame in node.outputs.items():
            pd.testing.assert_frame_equal(frame, actual[node_id][anchor], check_exact=True)
    assert 'evaluate_expression' not in artifact.source


def test_cli_accepts_workflow_python_and_ir(tmp_path, capsys):
    builder = WorkflowBuilder()
    builder.add_text_input(['value'], [['1']])
    workflow = parse(builder, tmp_path)
    original = tmp_path / 'phase_one.py'
    original.write_text(PythonGenerator().generate(workflow), encoding='utf-8')
    for index, source in enumerate([tmp_path / 'workflow.yxmd', original]):
        assert main(['readable', str(source), '--output', str(tmp_path / f'phase_two_{index}.py')]) == 0
    assert main(['readable', str(tmp_path / 'phase_two_0.ir.json'), '--output', str(tmp_path / 'from_ir.py')]) == 0
    assert 'generated' in capsys.readouterr().out


@pytest.mark.parametrize('control', [False,True])
def test_disabled_or_empty_control_keeps_formula_schema(tmp_path,control):
    builder = WorkflowBuilder()
    source = builder.add_text_input(['value'],[['2']])
    formula = builder.add_formula([('added','Int16','2','[value]+1')])
    container = builder._node('ControlContainer',
        '<Disabled value="False"/>' if control else '<Disabled value="True"/>', (100,100))
    builder.connect(source,formula)
    if control:
        trigger = builder.add_text_input(['signal'],[])
        builder.connect(trigger,container,target_anchor='Control')
    workflow = parse(builder,tmp_path)
    nodes = {node.node_id:node for node in workflow.nodes}
    if not control:
        nodes[str(container)].tool_type = 'ToolContainer'
    nodes[str(formula)].config['container_id'] = str(container)
    nodes[str(container)].config['child_node_ids'] = [str(formula)]
    expected = run_workflow_graph(workflow,WorkflowContext())
    _,actual = run_readable(workflow,tmp_path)
    frame = actual[str(formula)]['Output']
    assert frame.empty
    assert list(frame.columns) == ['value','added']
    assert str(frame['added'].dtype) == 'Int16'
    pd.testing.assert_frame_equal(expected.node_results[str(formula)].outputs['Output'],frame)


@pytest.mark.parametrize('disabled', [False,True])
def test_embedded_macro_with_nested_container_survives_source_removal(tmp_path,disabled):
    macro = tmp_path/'Double.yxmc'
    macro.write_text('''<AlteryxDocument><Nodes>
      <Node ToolID="1"><GuiSettings Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput"/><Properties><Configuration><Name>Input</Name></Configuration></Properties></Node>
      <Node ToolID="9"><GuiSettings Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer"/><Properties><Configuration><Disabled value="''' + str(disabled) + '''"/></Configuration></Properties><ChildNodes>
      <Node ToolID="2"><GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"/><Properties><Configuration><FormulaFields><FormulaField field="twice" expression="[x]*2" type="Int32" size="4"/></FormulaFields></Configuration></Properties></Node>
      </ChildNodes></Node>
      <Node ToolID="3"><GuiSettings Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput"/><Properties><Configuration><Name>Output</Name></Configuration></Properties></Node>
      </Nodes><Connections><Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
      <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection></Connections></AlteryxDocument>''',encoding='utf-8')
    builder = WorkflowBuilder()
    source = builder.add_text_input(['x'],[['2'],['3']])
    caller = builder._tool_id()
    builder.nodes_xml.append(f'<Node ToolID="{caller}"><GuiSettings/><Properties><Configuration/></Properties><EngineSettings Macro="Double.yxmc"/></Node>')
    builder.connect(source,caller)
    workflow = parse(builder,tmp_path)
    phase_one = tmp_path/'phase_one.py'
    phase_one.write_text(PythonGenerator().generate(workflow),encoding='utf-8')
    macro.unlink()
    preserved = read_phase_one(phase_one)
    expected = run_workflow_graph(preserved,WorkflowContext())
    _,actual = run_readable(preserved,tmp_path)
    pd.testing.assert_frame_equal(expected.node_results[str(caller)].outputs['Output'],actual[str(caller)]['Output'])
    assert len(actual[str(caller)]['Output']) == (0 if disabled else 2)


@pytest.mark.skipif(os.name != 'nt', reason='Benchmark exercises actual Windows batch workflow events')
def test_connected_benchmark_and_isolated_standalone(tmp_path):
    source = build_benchmark(tmp_path / 'sample', DATA)
    report = run_benchmark(source, tmp_path / 'acceptance')
    assert report['status'] == 'python_match'
    assert len(report['nodes']) >= 38
    assert len(report['artifacts']) == 8
    assert report['native_equivalence'] == 'unverified'
    standalone = tmp_path / 'independent'
    standalone.mkdir()
    shutil.copy(tmp_path / 'acceptance/readable.py', standalone / 'business.py')
    shutil.copytree(source.parent / 'data', standalone / 'data')
    for name in ('before.bat', 'after.bat'):
        shutil.copy(source.parent / name, standalone / name)
    output = standalone / 'output'
    argv = [str(standalone / 'business.py'), '--output-dir', str(output), '--event-working-dir', str(output), '--command-working-dir', str(output), '--allow-command', sys.executable]
    for name in ('before.bat', 'after.bat'):
        argv += ['--allow-command', str(standalone / name)]
    bootstrap = ('import sys,runpy,importlib.abc; '
        'exec("class BlockProject(importlib.abc.MetaPathFinder):\\n def find_spec(self,fullname,path=None,target=None):\\n  if fullname.startswith((\\\"alteryx2python\\\",\\\"alteryx_runtime\\\")): raise ImportError(fullname)"); '
        'sys.meta_path.insert(0,BlockProject()); sys.argv=' + repr(argv) + '; runpy.run_path(sys.argv[0],run_name="__main__")')
    completed = subprocess.run([sys.executable, '-I', '-c', bootstrap], cwd=standalone,
        capture_output=True, text=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
    assert completed.returncode == 0, completed.stderr
    actual = {path.relative_to(output).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
              for path in output.rglob('*') if path.is_file()}
    assert actual == report['artifacts']


@pytest.mark.skipif(os.name != 'nt', reason='Actual Windows batch events')
def test_same_compiled_program_accepts_changed_numeric_input(tmp_path):
    source = build_benchmark(tmp_path / 'sample', DATA)
    workflow = XmlWorkflowParser().parse(source)
    artifact = ReadablePythonGenerator().generate(workflow, delivery_profile='html-draft-v1')
    readable = {'__file__':str(tmp_path / 'editable.py')}
    exec(artifact.verification_source, readable)
    baseline = {}
    exec(PythonGenerator().generate(workflow), baseline)
    allowed = [sys.executable, str(source.parent / 'before.bat'), str(source.parent / 'after.bat')]
    for value in (5, 6.5, 7):
        expected_dir, actual_dir = tmp_path / f'baseline_{value}', tmp_path / f'readable_{value}'
        expected_dir.mkdir()
        expected, _ = baseline['run_workflow'](runtime_config={'answers':{'minimum_sepal_length':value},
            'input_dir':str(source.parent),'output_dir':str(expected_dir),'event_working_dir':str(expected_dir),
            'command_working_dir':str(expected_dir),
            'delivery_profile':'html-draft-v1','execute_commands':True,'redirect_sinks':True,'allowed_commands':allowed})
        checkpoints = {}
        readable['run_workflow'](minimum_sepal_length=value, input_dir=source.parent, output_dir=actual_dir,
            event_working_dir=actual_dir, command_working_dir=actual_dir, allowed_commands=allowed, checkpoints=checkpoints)
        for node_id, result in expected.node_results.items():
            for anchor, frame in result.outputs.items():
                pd.testing.assert_frame_equal(frame, checkpoints[node_id][anchor], check_exact=True)
    with pytest.raises(ValueError, match='maximum'):
        readable['run_workflow'](minimum_sepal_length=11, output_dir=tmp_path/'bad')
