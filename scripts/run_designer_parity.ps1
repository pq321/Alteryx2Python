[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Source,
    [Parameter(Mandatory)][string]$Output,
    [Parameter(Mandatory)][int]$DesignerProcessId,
    [string]$ExpectedFailures,
    [ValidateRange(5, 3600)][int]$TimeoutSeconds = 45,
    [ValidateRange(1, 16)][int]$Jobs = 4
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = $env:ALTERYX2PYTHON_PYTHON
if (-not $python) { $python = Join-Path $repo '.venv/Scripts/python.exe' }
$batch = Join-Path $PSScriptRoot 'parity_batch.py'
$designer = Join-Path $PSScriptRoot 'designer_click_run.ps1'
$ocr = Join-Path $PSScriptRoot 'designer_results_ocr.ps1'
$destination = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
if (Test-Path -LiteralPath $destination) { throw "Choose a new run directory: $destination" }
$native = Join-Path $destination 'native'
$report = Join-Path $native 'designer.json'
$classic = Join-Path $destination 'classic'

& $python $batch plan (Resolve-Path -LiteralPath $Source).Path --root $native
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$plan = Join-Path $native 'plan.json'
$cases = @(Get-Content -LiteralPath $plan -Raw | ConvertFrom-Json)
if (-not @($cases | Where-Object status -eq 'ready').Count) { exit 1 }

& pwsh -NoProfile -File $designer -Plan $plan -Report $report -DesignerProcessId $DesignerProcessId -TimeoutSeconds $TimeoutSeconds
if (-not (Test-Path -LiteralPath $report)) { exit 1 }
$ran = @(Get-Content -LiteralPath $report -Raw | ConvertFrom-Json).Count
$incompletePlan = $ran -ne $cases.Count -or @($cases | Where-Object status -ne 'ready').Count
& powershell.exe -NoProfile -File $ocr -Root $native
if ($LASTEXITCODE) { exit $LASTEXITCODE }

& $python $batch plan-amp --designer-report $report --output-dir $classic
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$classicPlan = Join-Path $classic 'plan.json'
$classicExit = 0
if (@(Get-Content -LiteralPath $classicPlan -Raw | ConvertFrom-Json).Count) {
    & pwsh -NoProfile -File $designer -Plan $classicPlan -Report (Join-Path $classic 'designer.json') -DesignerProcessId $DesignerProcessId -TimeoutSeconds $TimeoutSeconds
    $classicExit = $LASTEXITCODE
}

$attestArgs = @('attest-designer', $native, '--designer-report', $report,
    '--ocr-report', (Join-Path $native 'designer-ocr.json'), '--output', (Join-Path $native 'attestation.json'))
if ($ExpectedFailures) { $attestArgs += @('--expected-failures', (Resolve-Path -LiteralPath $ExpectedFailures).Path) }
& $python $batch @attestArgs
$attestExit = $LASTEXITCODE
& $python $batch verify-delivery $native --output-dir (Join-Path $destination 'delivery') --jobs $Jobs
$deliveryExit = $LASTEXITCODE
exit [int]([bool]($incompletePlan -or $classicExit -or $attestExit -or $deliveryExit))
