"""Exercise the actual compiler with the same contract as reference.py."""

import argparse
import ast
import csv
from difflib import unified_diff
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET

import pandas as pd

from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.generator.readable import ReadablePythonGenerator, read_phase_one
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.workflow_generator import WorkflowBuilder, escape

from reference import run_workflow as run_reference


EXAMPLE = Path(__file__).resolve().parent
PROFILE = 'html-draft-v1'


def build_workflow(path, *, by_product=False, include_reporting=True, include_email=True):
    builder = WorkflowBuilder()
    load = builder._node('DbFileInput',
        '<File FileFormat="0">transactions.csv</File><FormatSpecificOptions>'
        '<HeaderRow>True</HeaderRow><Delimeter>,</Delimeter><CodePage>65001</CodePage>'
        '</FormatSpecificOptions>', (50, 160))
    fields = [
        ('trade_id', 'transaction_id', 'V_WString', 16),
        ('trade_date', 'report_date', 'V_WString', 10),
        ('desk_region', 'region', 'V_WString', 16),
        ('product_code', 'product', 'V_WString', 16),
        ('booking_status', 'status', 'V_WString', 16),
        ('amount_minor', 'amount_cents', 'Int64', 8),
    ]
    selection = ''.join(
        f'<SelectField field="{old}" rename="{new}" selected="True" type="{dtype}" size="{size}"/>'
        for old, new, dtype, size in fields
    )
    rename = builder._node('Select', f'<SelectFields>{selection}</SelectFields>', (160, 160))
    eligible = builder.add_filter(
        '!IsNull([region]) AND [region] != "" AND [status] = "posted" AND '
        '!IsNull([amount_cents]) AND [amount_cents] >= 100', (270, 160))
    unique = builder.add_unique('transaction_id', (380, 160))
    keys = ['report_date', 'region', 'product'] if by_product else ['report_date', 'region']
    summary = builder.add_summarize(
        [(key, 'GroupBy', '') for key in keys] + [
            ('transaction_id', 'Count', 'transaction_count'), ('amount_cents', 'Sum', 'total_cents'),
        ], (490, 160))
    ordered = builder.add_sort([(key, 'Ascending') for key in keys], (600, 160))
    barrier = builder._node('BlockUntilDone', '', (710, 160))
    output = builder.add_csv_output('summary.csv', (830, 80))
    labels = {
        load: 'read_transactions', rename: 'rename_transaction_fields', eligible: 'select_posted_transactions',
        unique: 'deduplicate_transactions', summary: 'summarize_transactions', ordered: 'sort_summary',
        barrier: 'write_outputs_in_order', output: 'write_summary_csv',
    }
    builder.connect(load, rename)
    builder.connect(rename, eligible)
    builder.connect(eligible, unique, 'True')
    builder.connect(unique, summary, 'Unique')
    builder.connect(summary, ordered)
    builder.connect(ordered, barrier)
    builder.connect(barrier, output)
    if include_reporting:
        table = builder._node('PortfolioComposerTable',
            '<TableMode>Basic</TableMode><GroupingFields orderChanged="False"/>'
            '<Width>100%</Width><ShowHeader value="True"/><ShowBarGraph value="False"/>'
            '<TableFields orderChanged="False"><Field name="*Unknown" selected="True"/></TableFields>'
            '<TableStyles/><StyleRules/>', (830, 240))
        render = builder._node('PortfolioComposerRender',
            '<TempFileType/><OutputFile>report.html</OutputFile><BatchMode value="False"/>'
            '<DataField>Table</DataField><Separator>Continuous</Separator><EmbedDependencies value="False"/>'
            '<ShowHeader value="False"/><ShowFooter value="False"/><PortraitMode value="True"/>'
            '<PaperType Width="612" Height="792" Left="36" Right="36" Top="36" Bottom="36"/>',
            (960, 190))
        builder.connect(barrier, table, 'Output2')
        builder.connect(table, render)
        labels.update({table: 'build_report_table', render: 'write_html_report'})
        if include_email:
            subject = 'Posted transaction summary by product' if by_product else 'Posted transaction summary'
            draft = builder._node('Email',
                '<From>reports@example.invalid</From><To>reviewer@example.invalid</To>'
                f'<Subject>{escape(subject)}</Subject><Body>Table</Body>'
                '<Attachments><Attachment>summary.csv</Attachment></Attachments>', (960, 300))
            builder.connect(table, draft)
            labels[draft] = 'draft_summary_email'
    root = ET.fromstring(builder.render())
    for node in root.findall('./Nodes/Node'):
        node.find('./Properties/Annotation/Name').text = labels[int(node.attrib['ToolID'])]
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
    return [(str(eligible), 'True'), (str(unique), 'Unique'), (str(ordered), 'Output')]


class TableCells(HTMLParser):
    """Read display values without comparing HTML container or MIME formatting."""

    def __init__(self, source):
        super().__init__()
        self.rows = []
        self.cell = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.rows.append([])
        if tag in {'td', 'th'}:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in {'td', 'th'}:
            self.rows[-1].append(''.join(self.cell))
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def csv_rows(data):
    return list(csv.reader(StringIO(data.decode('utf-8-sig'))))


def outputs(directory):
    (draft,) = directory.glob('*.eml')
    message = BytesParser(policy=policy.default).parsebytes(draft.read_bytes())
    (attachment,) = message.iter_attachments()
    return {
        'csv': csv_rows((directory / 'summary.csv').read_bytes()),
        'html': TableCells((directory / 'report.html').read_text(encoding='utf-8')).rows,
        'headers': {name: str(message[name]) for name in ('From', 'To', 'Subject', 'X-Unsent')},
        'plain_text': message.get_body(preferencelist=('plain',)).get_content().strip(),
        'email_table': TableCells(message.get_body(preferencelist=('html',)).get_content()).rows,
        'attachment': [attachment.get_filename(), csv_rows(attachment.get_payload(decode=True))],
    }


def assert_outputs(expected_dir, actual_dir):
    expected = outputs(expected_dir)
    actual = outputs(actual_dir)
    for kind, value in expected.items():
        if actual[kind] != value:
            raise AssertionError(f'{actual_dir.name}: {kind} differs: {actual[kind]!r} != {value!r}')
    return actual


def execute_source(source, path):
    namespace = {'__file__': str(path), '__name__': 'pipeline_comparison'}
    exec(compile(source, str(path), 'exec'), namespace)
    return namespace['run_workflow']


def run_delivery(script, input_dir, output_dir):
    # Isolated Python with a different cwd exercises the delivered CLI and path handling.
    output_dir.mkdir()
    return subprocess.run([sys.executable, '-I', str(script), '--input-dir', str(input_dir),
                           '--output-dir', str(output_dir)], cwd=output_dir, capture_output=True,
                          text=True, timeout=60)


def run_case(root, input_file, *, by_product=False, reference_run=run_reference, empty_case=False):
    root.mkdir()
    shutil.copyfile(input_file, root / 'transactions.csv')
    workflow_file = root / 'transactions.yxmd'
    anchors = build_workflow(workflow_file, by_product=by_product)
    workflow = XmlWorkflowParser().parse(workflow_file)
    phase_one = root / 'phase_one.py'
    phase_one.write_text(PythonGenerator().generate(workflow), encoding='utf-8')
    artifact = ReadablePythonGenerator().generate(read_phase_one(phase_one), delivery_profile=PROFILE)
    readable = root / 'readable.py'
    artifact.write(readable)

    expected_dir = root / 'reference-output'
    expected_frames = reference_run(root, expected_dir)
    phase_one_dir = root / 'phase-one-output'
    phase_one_dir.mkdir()
    execute = execute_source(phase_one.read_text(encoding='utf-8'), phase_one)
    failures = {}
    try:
        result, _ = execute(runtime_config={
            'delivery_profile': PROFILE, 'output_dir': str(phase_one_dir), 'input_dir': str(root),
            'redirect_sinks': True,
        })
    except Exception as error:
        if not empty_case:
            raise
        failures['phase_one'] = f'{type(error).__name__}: {error}'
    verify_dir = root / 'phase-two-verification-output'
    checkpoints = {}
    try:
        execute_source(artifact.verification_source, readable)(
            input_dir=root, output_dir=verify_dir, checkpoints=checkpoints,
        )
    except Exception as error:
        if not empty_case:
            raise
        failures['phase_two_verification'] = f'{type(error).__name__}: {error}'
    delivery_dir = root / 'delivery-output'
    delivery = run_delivery(readable, root, delivery_dir)
    if delivery.returncode:
        if not empty_case:
            raise RuntimeError(delivery.stderr)
        failures['phase_two_delivery'] = delivery.stderr.strip()
    if failures:
        return {
            'status': 'mismatch', 'reference_summary': outputs(expected_dir)['csv'],
            'phase_results': {phase: failures.get(phase, 'completed') for phase in
                              ('phase_one', 'phase_two_verification', 'phase_two_delivery')},
        }
    if set(result.node_results) != set(checkpoints):
        raise AssertionError('Different Phase 1 and Phase 2 checkpoint sets')
    anchor_count = 0
    for node_id, baseline in result.node_results.items():
        actual = checkpoints[node_id]
        if set(baseline.outputs) != set(actual):
            raise AssertionError(f'Different anchor sets at node {node_id}')
        for anchor, frame in baseline.outputs.items():
            pd.testing.assert_frame_equal(frame, actual[anchor], check_dtype=True, check_exact=True)
            if frame.attrs != actual[anchor].attrs:
                raise AssertionError(f'Different Alteryx metadata at node {node_id}/{anchor}')
            anchor_count += 1
    for (node_id, anchor), expected_frame in zip(anchors, expected_frames, strict=True):
        actual = checkpoints[node_id][anchor].reset_index(drop=True)
        pd.testing.assert_frame_equal(expected_frame.reset_index(drop=True), actual,
                                      check_dtype=False, check_exact=True)

    baseline_artifacts = {file.name: file.read_bytes() for file in phase_one_dir.iterdir() if file.is_file()}
    for output_dir in (phase_one_dir, verify_dir, delivery_dir):
        result_artifacts = assert_outputs(expected_dir, output_dir)
        artifacts = {file.name: file.read_bytes() for file in output_dir.iterdir() if file.is_file()}
        if artifacts != baseline_artifacts:
            raise AssertionError(f'{output_dir.name}: generated artifact bytes differ')
    return {
        'status': 'match',
        'matched_phase_anchors': anchor_count, 'matched_business_checkpoints': len(anchors),
        'phase_nodes': len(checkpoints), 'matched_artifacts': sorted(baseline_artifacts),
        'summary': result_artifacts['csv'], 'subject': result_artifacts['headers']['Subject'],
    }


def edit_script(original_path, edited_path, replacements):
    original = original_path.read_text(encoding='utf-8')
    edited = original
    changed_lines = set()
    for before, after in replacements:
        if edited.count(before) != 1:
            raise ValueError(f'{original_path.name}: refresh the change experiment around {before!r}')
        changed_lines.add(edited[:edited.index(before)].count('\n') + 1)
        edited = edited.replace(before, after, 1)
    edited_path.write_text(edited, encoding='utf-8')
    patch = unified_diff(original.splitlines(keepends=True), edited.splitlines(keepends=True),
                         fromfile=original_path.name, tofile=edited_path.name)
    edited_path.with_suffix('.diff').write_text(''.join(patch), encoding='utf-8')
    return {
        'nonblank_lines': sum(bool(line.strip()) for line in original.splitlines()),
        'functions': sum(isinstance(node, ast.FunctionDef) for node in ast.walk(ast.parse(original))),
        'changed_locations': len(replacements), 'changed_lines': sorted(changed_lines),
    }


def run_change(root):
    subject_edit = ('Posted transaction summary', 'Posted transaction summary by product')
    group_keys = "['report_date', 'region']"
    product_keys = "['report_date', 'region', 'product']"
    reference = root / 'reference_by_product.py'
    readable = root / 'readable_by_product.py'
    metrics = {
        'reference': edit_script(EXAMPLE / 'reference.py', reference, [
            (f'GROUP_KEYS = {group_keys}', f'GROUP_KEYS = {product_keys}'), subject_edit,
        ]),
        'phase_two': edit_script(root / 'baseline' / 'readable.py', readable, [
            (f'SUMMARY_GROUP_KEYS_5 = {group_keys}', f'SUMMARY_GROUP_KEYS_5 = {product_keys}'),
            subject_edit,
        ]),
    }
    changed_workflow = root / 'by-product'
    reference_run = execute_source(reference.read_text(encoding='utf-8'), reference)
    regenerated = run_case(changed_workflow, EXAMPLE / 'transactions.csv',
                           by_product=True, reference_run=reference_run)
    edited_outputs = root / 'edited-phase-two-output'
    result = run_delivery(readable, changed_workflow, edited_outputs)
    if result.returncode:
        raise RuntimeError(result.stderr)
    assert_outputs(changed_workflow / 'delivery-output', edited_outputs)
    return {'status': 'match', 'measurements': metrics, 'regenerated': regenerated}


def run_native(root, engine):
    from alteryx2python.parity.runner import collect_native, compare_runs, execute_native, prepare, write_json

    source_dir = root / 'native-source'
    source_dir.mkdir()
    shutil.copyfile(EXAMPLE / 'transactions.csv', source_dir / 'transactions.csv')
    workflow = source_dir / 'transactions.yxmd'
    build_workflow(workflow, include_reporting=False)
    proof_dir = root / 'native-proof'
    prepare(workflow, proof_dir)
    execution = execute_native(proof_dir, engine, timeout=60)
    native = collect_native(proof_dir)
    write_json(proof_dir / 'native.json', native)
    python = json.loads((proof_dir / 'python.json').read_text(encoding='utf-8'))
    report = compare_runs(native, python)
    write_json(proof_dir / 'comparison.json', report)
    return {'status': report['status'], 'reason': execution.get('reason'), 'scope': 'data pipeline through CSV'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--engine', type=Path, help='Optional AlteryxEngineCmd executable for native probes')
    args = parser.parse_args()
    root = args.destination.resolve()
    root.mkdir(parents=True, exist_ok=False)
    baseline = run_case(root / 'baseline', EXAMPLE / 'transactions.csv')
    change = run_change(root)
    empty_fixture = root / 'no-eligible-transactions.csv'
    empty_fixture.write_text(
        'trade_id,trade_date,desk_region,product_code,booking_status,amount_minor\n'
        'T009,2026-10-13,EMEA,Rates,posted,99\n', encoding='utf-8',
    )
    empty = run_case(root / 'empty-result', empty_fixture, empty_case=True)
    preview = root / 'designer-report'
    preview.mkdir()
    shutil.copyfile(EXAMPLE / 'transactions.csv', preview / 'transactions.csv')
    build_workflow(preview / 'transaction-report.yxmd', include_email=False)
    native = run_native(root, args.engine) if args.engine else {'status': 'unverified'}
    report = {'baseline': baseline, 'change_request': change, 'empty_result': empty, 'native': native}
    (root / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'{root / "comparison.json"}: baseline={baseline["status"]}, change={change["status"]}, '
          f'empty={empty["status"]}, native={native["status"]}')
    return int(empty['status'] != 'match' or native['status'] not in {'match', 'unverified'})


if __name__ == '__main__':
    sys.exit(main())
