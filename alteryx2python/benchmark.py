"""Reproducible high-coverage workflow construction and two-phase acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import subprocess
from xml.etree import ElementTree as ET

import pandas as pd

from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.generator.readable import ReadablePythonGenerator, read_phase_one
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.workflow_generator import WorkflowBuilder, escape


DATA_URL = 'https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data'
DATA_SHA256 = '6f608b71a7317216319b4d27b4d9bc84e6abd734eda7872b71a458569e2656c0'


def _write_xml(path, root):
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def build_benchmark(destination, data_path):
    """Create an original, connected analytic app and local macro from public data."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    workflow_path = destination / 'comprehensive.yxwz'
    if workflow_path.exists():
        raise FileExistsError(workflow_path)
    data = Path(data_path).read_bytes()
    if hashlib.sha256(data).hexdigest() != DATA_SHA256:
        raise ValueError('Public Iris data digest differs from the reviewed snapshot')
    frame = pd.read_csv(data_path, header=None)
    if frame.shape != (150, 5) or frame.iloc[:, 4].nunique() != 3:
        raise ValueError('Unexpected Iris dataset structure')
    (destination / 'data').mkdir(exist_ok=True)
    (destination / 'data' / 'iris.data').write_bytes(data)
    (destination / 'before.bat').write_text('@echo off\necho before>before-event.txt\necho before>>events.log\n', encoding='ascii')
    (destination / 'after.bat').write_text('@echo off\necho after>after-event.txt\necho after>>events.log\n', encoding='ascii')
    (destination / 'data' / 'provenance.json').write_text(json.dumps({
        'source_url': DATA_URL, 'publisher': 'UCI Machine Learning Repository',
        'dataset': 'Iris', 'sha256': DATA_SHA256, 'rows': 150, 'columns': 5,
        'retrieved_at': '2026-11-11', 'license_reference': 'https://archive.ics.uci.edu/dataset/53/iris',
    }, indent=2) + '\n', encoding='utf-8')

    macro = WorkflowBuilder()
    mi = macro._node('MacroInput', '<Name>Input</Name><Abbrev>I</Abbrev>', (54, 100))
    mf = macro.add_formula([
        ('species', 'V_WString', '24', 'Replace([species], "Iris-", "")'),
        ('scaled_petal_length', 'Double', '8', '[petal_length] * FACTOR'),
    ])
    mo = macro._node('MacroOutput', '<Name>Output</Name><Abbrev>O</Abbrev>', (500, 100))
    macro.connect(mi, mf)
    macro.connect(mf, mo)
    mr = ET.fromstring(macro.render())
    runtime = mr.find('Properties/RuntimeProperties')
    if runtime is None:
        runtime = ET.SubElement(mr.find('Properties'), 'RuntimeProperties')
    for item in list(runtime):
        if item.tag in {'Actions', 'Questions', 'ModuleType'}:
            runtime.remove(item)
    ET.SubElement(runtime, 'ModuleType').text = 'Macro'
    runtime.append(ET.fromstring('<Questions><Question><Type>NumericUpDown</Type><Name>factor</Name><Default>1</Default></Question></Questions>'))
    runtime.append(ET.fromstring(f'<Actions><NoCondition><True><Action><Type>UpdateValue</Type><Variable>factor</Variable><Replace value="True"/><ReplaceText>FACTOR</ReplaceText><Destination>{mf}/FormulaFields/FormulaField[2]/@expression</Destination></Action></True></NoCondition></Actions>'))
    _write_xml(destination / 'NormalizeMeasurements.yxmc', mr)

    parallel = WorkflowBuilder()
    first_input = parallel._node('MacroInput', '<Name>Input1</Name>', (54,54))
    second_input = parallel._node('MacroInput', '<Name>Input2</Name>', (54,250))
    block = parallel._node('BlockUntilDone', '', (200,54))
    first_output = parallel._node('MacroOutput', '<Name>Output1</Name>', (400,54))
    gate_sample = parallel.add_sample('First','1')
    gate = parallel.add_formula([('__benchmark_gate','Byte','1','1')])
    gate_select = parallel.add_select([('__benchmark_gate','True')], include_unknown=False)
    append = parallel._node('AppendFields', '<CartesianMode>Error</CartesianMode><SelectConfiguration><Configuration><SelectFields><SelectField field="Source___benchmark_gate" selected="False"/><SelectField field="*Unknown" selected="True"/></SelectFields></Configuration></SelectConfiguration>', (500,250))
    second_output = parallel._node('MacroOutput', '<Name>Output2</Name>', (650,250))
    parallel.connect(first_input,block)
    parallel.connect(block,first_output)
    parallel.connect(block,gate_sample,'Output2')
    parallel.connect(gate_sample,gate)
    parallel.connect(gate,gate_select)
    parallel.connect(gate_select,append,target_anchor='Source')
    parallel.connect(second_input,append,target_anchor='Targets')
    parallel.connect(append,second_output)
    pr = ET.fromstring(parallel.render())
    ET.SubElement(pr.find('Properties/RuntimeProperties'),'ModuleType').text = 'Macro'
    meta = ET.SubElement(pr.find('Properties'),'MetaInfo')
    ET.SubElement(meta,'Name').text = 'Benchmark Parallel Block Until Done'
    ET.SubElement(meta,'MigrationContract').text = 'ordered-outputs-v1'
    _write_xml(destination / 'BenchmarkParallelBlock.yxmc',pr)

    builder = WorkflowBuilder()
    labels = {}
    def label(node_id, name):
        labels[str(node_id)] = name
        return node_id
    source = label(builder._node('DbFileInput', '<File FileFormat="0">data/iris.data</File><FormatSpecificOptions><HeaderRow>False</HeaderRow><Delimeter>,</Delimeter><CodePage>65001</CodePage></FormatSpecificOptions>', (54, 160)), 'load_measurements')
    declarations = [('F1', 'sepal_length', 'Double', 8), ('F2', 'sepal_width', 'Double', 8),
                    ('F3', 'petal_length', 'Double', 8), ('F4', 'petal_width', 'Double', 8), ('F5', 'species', 'V_WString', 32)]
    cfg = '<SelectFields>' + ''.join(f'<SelectField field="{old}" rename="{new}" selected="True" type="{kind}" size="{size}"/>' for old,new,kind,size in declarations) + '</SelectFields>'
    selected = label(builder._node('Select', cfg, (180,160)), 'declare_measurement_fields')
    builder.connect(source, selected)
    record = label(builder.add_record_id(), 'number_measurements')
    builder.connect(selected, record)
    # A genuine local standard macro, including a bound numeric question/action.
    macro_id = builder._tool_id()
    builder.nodes_xml.append(f'<Node ToolID="{macro_id}"><GuiSettings/><Properties><Configuration><Value name="factor">2</Value></Configuration></Properties><EngineSettings Macro="NormalizeMeasurements.yxmc"/></Node>')
    label(macro_id, 'normalize_species')
    builder.connect(record, macro_id)
    computed = label(builder.add_formula([
        ('measurement_key', 'V_WString', '64', '[species] + "|" + ToString([RecordID])'),
        ('report_date', 'Date', '10', '"2026-11-11"'),
        ('petal_cost', 'FixedDecimal', '12.2', '[scaled_petal_length] * 1.25'),
    ]), 'calculate_report_fields')
    builder.connect(macro_id, computed)
    filtered = label(builder.add_filter('[sepal_length] >= MIN_SEPAL'), 'filter_minimum_sepal_length')
    builder.connect(computed, filtered)
    split = label(builder._node('TextToColumns', '<Field>measurement_key</Field><Delimeters value="|"/><NumFields value="2"/><RootName>key_part</RootName><Flags value="0"/><ErrorHandling>Last</ErrorHandling>', (600,160)), 'split_measurement_key')
    builder.connect(filtered, split, 'True')
    unique = label(builder.add_unique('RecordID'), 'deduplicate_measurements')
    builder.connect(split, unique)
    sorted_id = label(builder.add_sort([('species', 'Ascending'), ('RecordID', 'Ascending')]), 'sort_measurements')
    builder.connect(unique, sorted_id, 'Unique')
    running = label(builder.add_running_total('scaled_petal_length', 'species'), 'calculate_running_totals')
    builder.connect(sorted_id, running)
    ranked = label(builder.add_rank('sepal_length'), 'rank_measurements')
    builder.connect(running, ranked)
    sample = label(builder.add_sample('First', 120), 'take_report_sample')
    builder.connect(ranked, sample)
    summary = label(builder.add_summarize([('species','GroupBy','species'), ('sepal_length','Avg','mean_sepal_length'), ('RecordID','Count','measurement_count'), ('scaled_petal_length','Sum','petal_total')]), 'summarize_species')
    builder.connect(sample, summary)
    parallel_id = builder._tool_id()
    builder.nodes_xml.append(f'<Node ToolID="{parallel_id}"><GuiSettings/><Properties><Configuration/></Properties><EngineSettings Macro="BenchmarkParallelBlock.yxmc"/></Node>')
    label(parallel_id,'sequence_independent_streams')
    builder.connect(summary,parallel_id,target_anchor='Input1')
    builder.connect(filtered,parallel_id,'False',target_anchor='Input2')
    rejected_sink = label(builder.add_csv_output('output/rejected_measurements.csv'),'write_rejected_measurements')
    builder.connect(parallel_id,rejected_sink,'Output2')
    lookup = label(builder.add_text_input(['species','report_group'], [['setosa','A'],['versicolor','B'],['virginica','C']]), 'load_report_groups')
    join_columns = ['Left_species', 'Left_mean_sepal_length', 'Left_measurement_count', 'Left_petal_total', 'Right_report_group']
    join_selection = ''.join(f'<SelectField field="{name}" rename="{name}" selected="True"/>' for name in join_columns)
    join = label(builder._node('Join', '<JoinInfo connection="Left"><Field field="species"/></JoinInfo><JoinInfo connection="Right"><Field field="species"/></JoinInfo><SelectConfiguration><Configuration outputConnection="Join"><SelectFields>' + join_selection + '</SelectFields></Configuration></SelectConfiguration>', (800,160)), 'join_report_groups')
    builder.connect(parallel_id, join, 'Output1', target_anchor='Left')
    builder.connect(lookup, join, target_anchor='Right')
    output_cfg = '<SelectFields>' + ''.join(f'<SelectField field="{field}" selected="True" type="{kind}" size="{size}"/>' for field,kind,size in [('Left_species','V_WString',24),('Left_mean_sepal_length','Double',8),('Left_measurement_count','Int32',4),('Left_petal_total','Double',8),('Right_report_group','V_WString',8)]) + '</SelectFields>'
    report_fields = label(builder._node('Select', output_cfg, (900,160)), 'declare_report_fields')
    builder.connect(join, report_fields, 'Join')
    barrier = label(builder._node('BlockUntilDone', '', (1050,160)), 'finish_outputs_in_order')
    builder.connect(report_fields, barrier)
    sink = label(builder.add_csv_output('output/species_summary.csv'), 'write_species_summary')
    builder.connect(barrier, sink)
    table = label(builder._node('PortfolioComposerTable', '<TableMode>Basic</TableMode><ShowHeader value="True"/>', (1200,250)), 'build_report_table')
    builder.connect(barrier, table, 'Output2')
    title = label(builder._node('PortfolioComposerText', '<Output>Report</Output><Message>Iris measurement report</Message>', (1000,350)), 'build_report_title')
    union = label(builder.add_union(), 'combine_report_fragments')
    builder.connect(title, union)
    builder.connect(table, union)
    layout = label(builder._node('PortfolioComposerLayout', '<Orientation>Vertical</Orientation><LayoutFields><Field name="Report" selected="True"/></LayoutFields>', (1400,300)), 'assemble_report')
    builder.connect(union, layout)
    render = label(builder._node('PortfolioComposerRender', '<TempFileType>html</TempFileType><OutputFile>iris_report.html</OutputFile><DataField>Report</DataField>', (1550,300)), 'write_html_report')
    builder.connect(layout, render)
    code = 'from pathlib import Path; Path("command-proof.txt").write_text("command completed\\n")'
    command = label(builder._node('RunCommand', f'<ProgramName>{escape(sys.executable)}</ProgramName><Arguments>{escape(subprocess.list2cmdline(["-c", code]))}</Arguments><WorkingDir/>', (1250,450)), 'run_postprocessing_command')
    builder.connect(barrier, command, 'Output3')
    mail = label(builder._node('Email', '<From>reports@example.invalid</From><To>reviewer@example.invalid</To><Subject>Iris measurement report</Subject><Body>Report</Body><Attachments><Attachment>iris_report.html</Attachment></Attachments>', (1700,450)), 'draft_report_email')
    builder.connect(layout, mail)
    container = label(builder._node('ControlContainer', '<Caption>Draft after outputs finish</Caption><Disabled value="False"/>', (1600,450)), 'control_email_delivery')
    builder.connect(command, container, target_anchor='Control')
    browse = label(builder._node('BrowseV2', '', (1850,450)), 'inspect_completion')
    builder.connect(container, browse, 'Log')
    # Independent numeric/string branches exercise additional ordinary tool templates.
    transpose = label(builder.add_transpose(['species'], ['sepal_length','petal_length']), 'reshape_measurements_long')
    builder.connect(macro_id, transpose)
    crosstab = label(builder.add_crosstab('species', 'Name', 'Value', 'Sum'), 'reshape_measurements_wide')
    builder.connect(transpose, crosstab)
    regex = label(builder._node('RegEx', '<Field>measurement_key</Field><RegExExpression value="\\|"/><Method>Replace</Method><Replace expression="_"/>', (500,700)), 'normalize_measurement_key')
    builder.connect(computed, regex)
    auto = label(builder._node('AutoField', '', (600,700)), 'infer_field_widths')
    builder.connect(regex, auto)
    info = label(builder._node('FieldInfo', '', (750,700)), 'inspect_field_contracts')
    builder.connect(auto, info)
    generated = label(builder._node('GenerateRows', '<UpdateField value="False"/><CreateField_Name>replicate</CreateField_Name><CreateField_Type>Int32</CreateField_Type><CreateField_Size>4</CreateField_Size><Expression_Init>1</Expression_Init><Expression_Cond>[replicate] &lt;= 2</Expression_Cond><Expression_Loop>[replicate] + 1</Expression_Loop>', (800,700)), 'generate_measurement_replicates')
    builder.connect(macro_id, generated)
    multi = label(builder._node('MultiFieldFormula', '<Fields><Field name="sepal_length"/><Field name="petal_length"/></Fields><CopyOutput value="True"/><NewFieldAddOn>_doubled</NewFieldAddOn><NewFieldAddOnPos>Suffix</NewFieldAddOnPos><Expression>[_CurrentField_] * 2</Expression>', (950,700)), 'scale_multiple_measurements')
    builder.connect(generated, multi)
    previous = label(builder.add_multi_row_formula('[scaled_petal_length] - [Row-1:scaled_petal_length]', 'petal_delta'), 'compare_previous_measurement')
    builder.connect(multi, previous)
    root = ET.fromstring(builder.render())
    nodes = root.find('Nodes')
    for element in root.iter('Node'):
        props = element.find('Properties')
        annotation = props.find('Annotation')
        if annotation is None:
            annotation = ET.SubElement(props,'Annotation')
        name = ET.SubElement(annotation, 'Name') if annotation.find('Name') is None else annotation.find('Name')
        name.text = labels.get(element.get('ToolID'), '')
    # Container membership is structural XML, not a disconnected cosmetic node.
    control_node = nodes.find(f'Node[@ToolID="{container}"]')
    mail_node = nodes.find(f'Node[@ToolID="{mail}"]')
    nodes.remove(mail_node)
    ET.SubElement(control_node, 'ChildNodes').append(mail_node)
    structural = ET.SubElement(nodes, 'Node', ToolID='1000')
    ET.SubElement(structural, 'GuiSettings', Plugin='AlteryxGuiToolkit.ToolContainer.ToolContainer')
    props = ET.SubElement(structural,'Properties')
    ET.SubElement(props,'Configuration').append(ET.fromstring('<Caption>Measurement preparation</Caption>'))
    children = ET.SubElement(structural,'ChildNodes')
    for node_id in (selected, record):
        child = nodes.find(f'Node[@ToolID="{node_id}"]')
        nodes.remove(child)
        children.append(child)
    props = root.find('Properties')
    runtime = props.find('RuntimeProperties')
    if runtime is None:
        runtime = ET.SubElement(props,'RuntimeProperties')
    for item in list(runtime):
        if item.tag in {'Actions', 'Questions', 'ModuleType'}:
            runtime.remove(item)
    ET.SubElement(runtime,'ModuleType').text = 'Wizard'
    runtime.append(ET.fromstring('<Questions><Question><Type>NumericUpDown</Type><Name>minimum_sepal_length</Name><Default>5</Default><Minimum>0</Minimum><Maximum>10</Maximum></Question></Questions>'))
    runtime.append(ET.fromstring(f'<Actions><NoCondition><True><Action><Type>UpdateValue</Type><Variable>minimum_sepal_length</Variable><Replace value="True"/><ReplaceText>MIN_SEPAL</ReplaceText><Destination>{filtered}/Expression</Destination></Action></True></NoCondition></Actions>'))
    events = props.find('Events')
    if events is None:
        events = ET.SubElement(props,'Events')
    ET.SubElement(events,'Enabled',value='True')
    for when, script in [('Before','before.bat'),('After','after.bat')]:
        event = ET.SubElement(events,'Event')
        ET.SubElement(event,'When').text = when
        ET.SubElement(event,'SendMail',value='False')
        ET.SubElement(event,'cmd_Program').text = script
        ET.SubElement(event,'cmd_CommandLine').text = ''
        ET.SubElement(event,'cmd_WorkingDir').text = ''
        ET.SubElement(event,'cmd_Timeout',value='30')
    _write_xml(workflow_path, root)
    return workflow_path


def run_benchmark(source, destination, *, answers=None):
    """Execute the actual generated scripts and compare checkpoints and artifacts."""
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    source = Path(source).resolve()
    workflow = XmlWorkflowParser().parse(source)
    baseline_path = destination / 'phase_one.py'
    baseline_path.write_text(PythonGenerator().generate(workflow), encoding='utf-8')
    artifact = ReadablePythonGenerator().generate(read_phase_one(baseline_path), answers=answers, delivery_profile='html-draft-v1')
    artifact.write(destination / 'readable.py')
    baseline_dir, readable_dir = destination / 'baseline-output', destination / 'readable-output'
    baseline_dir.mkdir()
    readable_dir.mkdir()
    allowed = [sys.executable, str(source.parent / 'before.bat'), str(source.parent / 'after.bat')]
    runtime = {'delivery_profile': 'html-draft-v1', 'execute_commands': True,
               'allowed_commands': allowed, 'output_dir': str(baseline_dir), 'input_dir': str(source.parent),
               'event_working_dir': str(baseline_dir), 'command_working_dir': str(baseline_dir), 'redirect_sinks': True, 'answers': answers or {}}
    # Redirect only sinks; the original workflow and source data remain untouched.
    baseline_ns = {'__file__': str(baseline_path), '__name__': 'benchmark_phase_one'}
    exec(compile(baseline_path.read_text(encoding='utf-8'), str(baseline_path), 'exec'), baseline_ns)
    result, _ = baseline_ns['run_workflow'](runtime_config=runtime)
    readable_ns = {'__file__': str(destination / 'readable.py'), '__name__': 'benchmark_readable'}
    exec(compile(artifact.verification_source, str(destination / 'readable.py'), 'exec'), readable_ns)
    checkpoints = {}
    readable_ns['run_workflow'](input_dir=source.parent, output_dir=readable_dir, allowed_commands=allowed,
                               event_working_dir=readable_dir, command_working_dir=readable_dir, checkpoints=checkpoints)
    comparisons = []
    for node_id, baseline in result.node_results.items():
        actual = checkpoints.get(node_id)
        if actual is None or set(actual) != set(baseline.outputs):
            raise AssertionError(f'Missing/different readable anchors at node {node_id}')
        for anchor, expected in baseline.outputs.items():
            pd.testing.assert_frame_equal(expected, actual[anchor], check_dtype=True, check_exact=True)
            if expected.attrs != actual[anchor].attrs:
                raise AssertionError(f'Field contract metadata mismatch at {node_id}/{anchor}')
        comparisons.append({'node_id': node_id, 'tool_type': baseline.tool_type, 'anchors': list(actual), 'status': 'match'})
    baseline_files = {path.relative_to(baseline_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in baseline_dir.rglob('*') if path.is_file()}
    readable_files = {path.relative_to(readable_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in readable_dir.rglob('*') if path.is_file()}
    if baseline_files != readable_files:
        raise AssertionError(f'Artifact mismatch: {baseline_files} != {readable_files}')
    # The shipped source has no checkpoint instrumentation. Execute it as well,
    # so acceptance cannot certify only the verification variant.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix='delivery-check-', dir=destination) as temporary:
        delivery_dir = Path(temporary)
        delivered = {'__file__': str(destination / 'readable.py'), '__name__': 'benchmark_delivery'}
        exec(compile(artifact.source, str(destination / 'readable.py'), 'exec'), delivered)
        delivered['run_workflow'](input_dir=source.parent, output_dir=delivery_dir, allowed_commands=allowed,
            event_working_dir=delivery_dir, command_working_dir=delivery_dir)
        delivery_files = {path.relative_to(delivery_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in delivery_dir.rglob('*') if path.is_file()}
        if delivery_files != readable_files:
            raise AssertionError('Delivered/instrumented artifact mismatch')
    report = {'status': 'python_match', 'native_equivalence': 'unverified',
              'source_sha256': workflow.source_hash, 'answers': answers or {},
              'nodes': comparisons, 'tool_types': sorted({node.tool_type for node in workflow.nodes}),
              'artifacts': baseline_files, 'generated_sha256': artifact.manifest['generated_sha256'],
              'delivery_execution': 'match', 'verification_sha256': artifact.manifest['verification_sha256']}
    (destination / 'acceptance.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
