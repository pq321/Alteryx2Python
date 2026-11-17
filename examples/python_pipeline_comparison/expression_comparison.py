"""Compare nested Formula and Filter expressions across both Python phases."""

import argparse
from calendar import monthrange
from datetime import datetime
from hashlib import md5
import json
import math
from pathlib import Path
import runpy
import subprocess
import sys

import pandas as pd

from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.generator.readable import ReadablePythonGenerator, read_phase_one
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.parity.runner import file_hash, verify_manifest
from alteryx2python.workflow_generator import WorkflowBuilder
from alteryx2python.yxdb_file import read_yxdb_records


ROWS = [
    ('T1', '  Alpha Beta 12  ', '2024-02-10 16:30:45', '2.25'),
    ('T2', '  Beta Zulu 99  ', '2024-03-15 08:10:25', '3.25'),
    ('T3', ' Alpha Beta 3 and 5 ', '2024-04-16 09:17:31', '4.25'),
]
SOURCE_COLUMNS = ['Id', 'Text', 'Stamp', 'Value']
FORMULAS = [
    ('Word1', 'V_WString', '24', 'GetWord(Trim([Text]), 1)'),
    ('Part', 'V_WString', '16', 'Substring("Alteryx", 2, 3)'),
    ('MonthStart', 'V_WString', '19', 'DateTimeTrim(DateTimeParse([Stamp], "%Y-%m-%d %H:%M:%S"), "month")'),
    ('DigitGroups', 'Int32', '4', 'REGEX_CountMatches([Text], "[0-9]+")'),
    ('AmountCeiling', 'Double', '8', 'Ceil([Value])'),
    ('LoanPayment', 'Double', '8', 'FinancePMT(0.05 / 12, 360, 200000, 0, 0)'),
    ('LoanRounded', 'Double', '8', 'Round([LoanPayment], 0.01)'),
    ('Fingerprint', 'V_WString', '32', 'MD5_ASCII("a")'),
    ('MissingCeiling', 'Double', '8', 'Ceil(Null())'),
    ('EndMonth', 'V_WString', '19', 'DateTimeTrim([Stamp], "lastofmonth")'),
    ('CeilMultiple', 'Double', '8', 'Ceil(2.3, 0.5)'),
    ('FloorMultiple', 'Double', '8', 'Floor(0 - 2.3, 0.5)'),
    ('FindIndex', 'Int32', '4', 'FindString("Hello", "ll")'),
    ('EndsDefault', 'Bool', '1', 'EndsWith("ALPHA", "ha")'),
    ('EndsSensitive', 'Bool', '1', 'EndsWith("ALPHA", "ha", 0)'),
    ('RoundPositive', 'Double', '8', 'Round(2.5, 1)'),
    ('RoundNegative', 'Double', '8', 'Round(0 - 2.5, 1)'),
    ('RoundZero', 'Double', '8', 'Round(2.5, 0)'),
    ('WordMissing', 'V_WString', '20', 'GetWord("short text", 3)'),
    ('WordNegative', 'V_WString', '20', 'GetWord("short text", 0 - 1)'),
    ('WordNull', 'V_WString', '20', 'GetWord(Null(), 0)'),
    ('SubstringNegative', 'V_WString', '20', 'Substring("Alteryx", 0 - 2, 3)'),
    ('RegexpDefault', 'Int32', '4', 'REGEX_CountMatches("AaA", "a")'),
    ('MIRR', 'Double', '8', 'FinanceMIRR(0.1, 0.1, 0 - 100, 50, 80)'),
]
COLUMNS = SOURCE_COLUMNS + [name for name, *_ in FORMULAS]
PREDICATE = ('(GetWord(UpperCase(Trim([Text])), 1) = "BETA" '
             'AND REGEX_CountMatches([Text], "[0-9]+") = 1) OR Ceil([Value]) > 6')


def expected_outputs():
    """Independent Python calculation for the same fixture and branch conditions."""
    rate = 0.05 / 12
    payment = -rate * 200_000 / (1 - (1 + rate) ** -360)
    mirr = math.sqrt((50 * 1.1 + 80) / 100) - 1
    calculated, matched, rejected = [], [], []
    for identifier, text, timestamp, value in ROWS:
        date = datetime.fromisoformat(timestamp)
        word = text.split()[1]
        groups = sum(token.isdigit() for token in text.split())
        ceiling = math.ceil(float(value))
        first_day = date.replace(day=1, hour=0, minute=0, second=0)
        last_day = date.replace(day=monthrange(date.year, date.month)[1], hour=23, minute=59, second=59)
        row = [identifier, text, timestamp, float(value), word, 'ter', first_day.isoformat(sep=' '),
               groups, ceiling, payment, round(payment, 2), md5(b'a').hexdigest(), None,
               last_day.isoformat(sep=' '), 2.5, -2.5, 2, True, False, 3, -2, None,
               None, 'short', None, 'A', 3, mirr]
        calculated.append(row)
        (matched if (word.upper() == 'BETA' and groups == 1) or ceiling > 6 else rejected).append(row)
    return {'Output': calculated, 'True': matched, 'False': rejected}


def build_workflow(path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(SOURCE_COLUMNS, ROWS, (55, 160))
    typed = builder.add_select([(name, 'True') for name in SOURCE_COLUMNS], include_unknown=False,
                               field_types={'Value': ('Double', 8)}, position=(165, 160))
    formula = builder.add_formula(FORMULAS, (275, 160))
    filtered = builder.add_filter(PREDICATE, (405, 160))
    builder.connect(source, typed)
    builder.connect(typed, formula)
    builder.connect(formula, filtered)
    sinks = [(formula, 'Output', 'formula.csv', (415, 250)),
             (filtered, 'True', 'true.csv', (535, 115)),
             (filtered, 'False', 'false.csv', (535, 205))]
    for tool, anchor, filename, position in sinks:
        builder.connect(tool, builder.add_csv_output(filename, position), anchor)
    path.write_text(builder.render(), encoding='utf-8')
    return {'Output': str(formula), 'True': str(filtered), 'False': str(filtered)}


def compare_rows(actual, expected, anchor):
    if len(actual) != len(expected):
        raise AssertionError(f'{anchor}: expected {len(expected)} rows, got {len(actual)}')
    for index, (left, right) in enumerate(zip(actual, expected, strict=True), 1):
        for column, actual_value, expected_value in zip(COLUMNS, left, right, strict=True):
            if pd.isna(actual_value):
                actual_value = None
            elif isinstance(actual_value, datetime):
                actual_value = actual_value.isoformat(sep=' ')
            if column in {'LoanPayment', 'MIRR'}:
                matches = actual_value is not None and math.isclose(actual_value, expected_value, rel_tol=1e-13)
            else:
                matches = actual_value == expected_value
            if not matches:
                raise AssertionError(f'{anchor}, row {index}, {column}: {actual_value!r} != {expected_value!r}')


def compare_designer(source, proof, anchors, expected):
    manifest = verify_manifest(proof)
    if manifest['source_sha256'] != file_hash(source):
        raise ValueError('Designer probes belong to a different workflow')
    output_types = {name: dtype for name, dtype, *_ in FORMULAS}
    for anchor, expected_rows in expected.items():
        matches = [item for item in manifest['probes'] if (item['node_id'], item['anchor']) == (anchors[anchor], anchor)]
        (probe,) = matches
        schema, rows = read_yxdb_records(proof / probe['file'])
        if [field['name'] for field in schema] != COLUMNS:
            raise AssertionError(f'Designer {anchor} column order differs')
        for field in schema:
            if field['name'] in output_types and field['type'] != output_types[field['name']]:
                raise AssertionError(f"Designer {anchor} type differs for {field['name']}")
        compare_rows(rows, expected_rows, f'Designer {anchor}')


def run(destination, *, designer_probes=None):
    destination = destination.resolve()
    destination.mkdir(parents=True)
    source = destination / 'catalog-formula-native.yxmd'
    anchors = build_workflow(source)
    phase_one = destination / 'phase_one.py'
    phase_one.write_text(PythonGenerator().generate(XmlWorkflowParser().parse(source)), encoding='utf-8')
    baseline_dir = destination / 'phase-one-output'
    baseline_dir.mkdir()
    result, _ = runpy.run_path(str(phase_one))['run_workflow'](
        runtime_config={'output_dir': str(baseline_dir), 'redirect_sinks': True},
    )
    artifact = ReadablePythonGenerator().generate(read_phase_one(phase_one))
    phase_two = destination / 'readable.py'
    artifact.write(phase_two)
    verify = {'__file__': str(phase_two)}
    exec(compile(artifact.verification_source, str(phase_two), 'exec'), verify)
    checkpoints = {}
    verify['run_workflow'](output_dir=destination / 'verification-output', checkpoints=checkpoints)

    expected = expected_outputs()
    for anchor, node in anchors.items():
        baseline = result.node_results[node].outputs[anchor]
        generated = checkpoints[node][anchor]
        pd.testing.assert_frame_equal(baseline, generated, check_exact=True)
        if baseline.attrs != generated.attrs or list(baseline.columns) != COLUMNS:
            raise AssertionError(f'{anchor} metadata differs')
        compare_rows(list(baseline.itertuples(index=False, name=None)), expected[anchor], anchor)

    delivery_dir = destination / 'delivery-output'
    subprocess.run([sys.executable, '-I', str(phase_two), '--output-dir', str(delivery_dir)],
                   cwd=destination, check=True, capture_output=True, timeout=60)
    files = ['formula.csv', 'true.csv', 'false.csv']
    for filename in files:
        if (baseline_dir / filename).read_bytes() != (delivery_dir / filename).read_bytes():
            raise AssertionError(f'Delivered {filename} differs from Phase 1')

    if designer_probes:
        compare_designer(source, designer_probes, anchors, expected)
    report = {'status': 'match', 'designer': 'match' if designer_probes else 'unverified',
              'rows': {anchor: len(rows) for anchor, rows in expected.items()}, 'artifacts': files}
    (destination / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--designer-probes', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.destination, designer_probes=args.designer_probes), indent=2))
