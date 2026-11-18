"""Headless checks for the manifest-to-Designer answer contract."""

import json
import shutil
import subprocess
import sys
import time
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


@pytest.mark.skipif(sys.platform != "win32" or shutil.which("pwsh") is None, reason="Windows PowerShell 7 is required")
@pytest.mark.parametrize("timeout_kind", ["stage", "case"])
def test_designer_watchdog_reports_blocked_stage_and_stops_worker(tmp_path, timeout_kind):
    worker = tmp_path / "blocked worker.ps1"
    worker.write_text(
        """
param([switch]$Worker, [string]$Report, [string]$TimeoutKind)
$now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$progress = @{
    stage = 'click Finish'; workflow = 'blocked.yxwz'; designer_pid = 4321; session = 'reused'
    case_index = 1; stage_deadline = $now + $(if ($TimeoutKind -eq 'stage') { 700 } else { 30000 })
    case_deadline = $now + $(if ($TimeoutKind -eq 'case') { 700 } else { 30000 })
}
Set-Content -LiteralPath "$Report.tmp" -Value '[{"status":"outputs_ready","workflow":"first.yxmd"}]'
[IO.File]::Move("$Report.tmp", $Report)
$progress | ConvertTo-Json | Set-Content -LiteralPath "$Report.progress.tmp"
[IO.File]::Move("$Report.progress.tmp", "$Report.progress")
Start-Sleep -Seconds 40
""",
        encoding="utf-8",
    )
    script = tmp_path / "test supervisor.ps1"
    script.write_text(
        r"""
$ErrorActionPreference = 'Stop'
$runner, $worker, $report, $kind = $args
$ast = [System.Management.Automation.Language.Parser]::ParseFile($runner, [ref]$null, [ref]$null)
$functions = @('Write-DesignerJson', 'New-DesignerBlocked', 'Read-DesignerProgress', 'Invoke-DesignerSupervisor')
foreach ($name in $functions) {
    $function = $ast.Find({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $false)
    $definition = $function.Extent.Text.Replace('Local\Alteryx2Python.DesignerBatch', "Local\Alteryx2Python.DesignerBatch.Test.$PID")
    Invoke-Expression $definition
}
exit (Invoke-DesignerSupervisor $worker $report @('-TimeoutKind', $kind) 10)
""",
        encoding="utf-8",
    )
    report = tmp_path / "designer-run.json"
    started = time.monotonic()
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(script), str(RUNNER), str(worker), str(report), timeout_kind],
        capture_output=True, text=True, timeout=15,
    )
    assert time.monotonic() - started < 10
    assert result.returncode == 1
    first, blocked = json.loads(report.read_text(encoding="utf-8"))
    assert first == {"status": "outputs_ready", "workflow": "first.yxmd"}
    assert blocked == {
        "status": "blocked", "workflow": "blocked.yxwz", "stage": "click Finish",
        "designer_pid": 4321, "session": "reused", "reason": "automation_timeout",
        "detail": "Designer automation timed out during 'click Finish'.",
    }
    assert list(tmp_path.glob("designer-run.json.*")) == []


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell 7 is required")
def test_designer_selects_an_available_session_with_workflows_open(tmp_path):
    script = tmp_path / "select sessions.ps1"
    script.write_text(
        """
$ErrorActionPreference = 'Stop'
$ast = [System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$null, [ref]$null)
$selector = $ast.Find({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Select-DesignerCandidate'
}, $false)
Invoke-Expression $selector.Extent.Text
$busy = @{ id = 1; ready = $false; blank = $true }
$open = @{ id = 2; ready = $true; blank = $false }
$blank = @{ id = 3; ready = $true; blank = $true }
$other = @{ id = 4; ready = $true; blank = $false }
$ambiguity = try { Select-DesignerCandidate @($open, $other) } catch { $_.Exception.Message }
@{
    reused = (Select-DesignerCandidate @($busy, $open)).id
    preferred = (Select-DesignerCandidate @($open, $blank)).id
    unavailable = $null -eq (Select-DesignerCandidate @($busy))
    ambiguity = $ambiguity
} | ConvertTo-Json
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(script), str(RUNNER)],
        capture_output=True, text=True, check=True, timeout=15,
    )
    observed = json.loads(result.stdout)
    assert observed["reused"] == 2
    assert observed["preferred"] == 3
    assert observed["unavailable"]
    assert "PIDs 2, 4" in observed["ambiguity"]


def test_prepared_cases_have_distinct_titles_in_a_reused_designer_window(tmp_path):
    source = app_fixture(tmp_path)
    first = prepare_migration(source, tmp_path / "first")
    second = prepare_migration(source, tmp_path / "second")
    first_name = Path(first["native_workflow"]).name
    second_name = Path(second["native_workflow"]).name
    assert first_name != second_name
    assert Path(first_name).suffix == Path(second_name).suffix == ".yxwz"
