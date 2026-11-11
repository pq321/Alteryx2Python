import json
from pathlib import Path

from alteryx2python.benchmark_inventory import build_inventory
from alteryx2python.cli import main
from alteryx2python.workflow_generator import WorkflowBuilder


def test_inventory_keeps_all_official_rows_and_distinguishes_compile_from_proof(tmp_path):
    samples = tmp_path / 'samples'
    samples.mkdir()
    builder = WorkflowBuilder()
    source = builder.add_text_input(['value'],[['1']])
    formula = builder.add_formula([('twice','Int32','4','[value]*2')])
    builder.connect(source,formula)
    (samples/'valid.yxmd').write_text(builder.render(),encoding='utf-8')
    (samples/'invalid.yxmd').write_text('not XML',encoding='utf-8')
    output = tmp_path/'inventory'
    summary = build_inventory(output,samples)
    official = json.loads((Path(__file__).resolve().parents[1]/'docs/tools/official_inventory.json').read_text(encoding='utf-8'))
    report = json.loads((output/'coverage.json').read_text(encoding='utf-8'))
    assert len(report['tools']) == len(official['tools'])
    assert [row['plugin_id'] for row in report['tools']] == [row['plugin_id'] for row in official['tools']]
    assert summary['native_verified_rows'] == 0 and not summary['fully_covered']
    assert len(summary['parse_errors']) == 1
    assert summary['python_differential_rows'] == 0
    assert summary['compiled_rows'] >= 2
    missing = [row for row in report['tools'] if not row['sample_present']]
    assert missing and all(row['blocker'] for row in missing)
    assert all(row['python_differential'] == 'unverified' for row in report['tools'])


def test_incomplete_inventory_cli_returns_nonzero(tmp_path,capsys):
    assert main(['benchmark','inventory','--output',str(tmp_path/'inventory'),'--samples',str(tmp_path/'missing')]) == 2
    assert json.loads(capsys.readouterr().out)['sample_rows'] == 0
