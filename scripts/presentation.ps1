# Run from the repository root, using its virtual environment or the active Python.
$python = $env:ALTERYX2PYTHON_PYTHON
if (-not $python) {
    $venv = Join-Path $PSScriptRoot '../.venv/Scripts/python.exe'
    $python = if (Test-Path -LiteralPath $venv -PathType Leaf) { $venv } else { 'python' }
}
if ($MyInvocation.ExpectingInput) {
    $input | & $python -m alteryx2python.cli demo @args
} else {
    & $python -m alteryx2python.cli demo @args
}
exit $LASTEXITCODE
