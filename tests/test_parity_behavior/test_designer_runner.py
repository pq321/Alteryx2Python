"""Headless checks for the manifest-to-Designer answer contract."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from alteryx2python.parity.migration import prepare_migration
from test_migration import app_fixture


RUNNER = Path(__file__).resolve().parents[2] / "scripts" / "designer_click_run.ps1"


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell 7 is required")
def test_designer_preparation_uses_recorded_date_and_calendar_positions(tmp_path):
    source = app_fixture(tmp_path)
    case = tmp_path / "case"
    prepare_migration(source, case, supplied={"report_date": "2026-10-13"})
    code = """
$ErrorActionPreference = 'Stop'
$scriptFile = $args[0]
$case = $args[1]
$ast = [System.Management.Automation.Language.Parser]::ParseFile($scriptFile, [ref]$null, [ref]$null)
foreach ($name in @('Get-PreparedCase', 'Get-CalendarCell')) {
    $function = $ast.Find({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $false)
    Invoke-Expression $function.Extent.Text
}
$prepared = Get-PreparedCase @{ run_dir = $case }
@{
    answers = $prepared.answers
    cells = @(
        Get-CalendarCell ([datetime]'2026-10-13')
        Get-CalendarCell ([datetime]'2026-11-01')
        Get-CalendarCell ([datetime]'2026-11-18')
        Get-CalendarCell ([datetime]'2027-01-03')
    )
} | ConvertTo-Json -Depth 6
"""
    script = tmp_path / "check.ps1"
    script.write_text(code, encoding="utf-8")
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(script), str(RUNNER), str(case / "native")],
        capture_output=True, text=True, check=True, timeout=30,
    )
    observed = json.loads(result.stdout)
    answers = {answer["name"]: answer for answer in observed["answers"]}
    assert answers["report_date"]["value"] == "2026-10-13"
    assert answers["report_date"]["kind"] == "Date"
    assert Path(answers["source_file"]["value"]).is_relative_to(case / "inputs")
    assert observed["cells"] == [16, 7, 24, 7]
