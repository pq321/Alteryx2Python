# CLI learning examples

Run commands from the repository root using the installed project environment.
Use fresh result directories.

```powershell
.\.venv\Scripts\python.exe -m alteryx2python.cli generate-workflow --spec examples\cli\branch.json --output reports\demo\branch.yxmd --python-output reports\demo\branch.py
.\.venv\Scripts\python.exe reports\demo\branch.py --output-dir reports\demo\branch-results
.\.venv\Scripts\python.exe -m alteryx2python.cli run-python examples\cli\parameter-app.yxwz --answers examples\cli\answers.json --output-dir reports\demo\app-results
.\.venv\Scripts\python.exe -m alteryx2python.cli run-python examples\cli\standard-macro.yxmd --output-dir reports\demo\standard-results
.\.venv\Scripts\python.exe -m alteryx2python.cli run-python examples\cli\batch-macro.yxmd --output-dir reports\demo\batch-results
.\.venv\Scripts\python.exe -m alteryx2python.cli run-python examples\cli\iterative-macro.yxmd --output-dir reports\demo\iterative-results
.\.venv\Scripts\python.exe -m alteryx2python.cli proof-suite --cases examples\cli\proof-cases.json --out-dir reports\demo\native-proof
```

Expected Python results: branch `twice=6`; app/standard `result`/`y=6,15`;
batch `y=6,15,8,20`; iterative `x=0,0` on the Done output.
The proof manifest tests macro boundary outputs. This host records actual
EngineCmd license blocking; those attempts are not native equivalence passes.

To modify configuration through a native-looking interface, inspect
parameter-app.yxwz and Factor.yxmc. Their RuntimeProperties contain actual
Questions/Actions shapes; caller values appear in standard-macro.yxmd.
BatchFactor.yxmc has one ControlParam; Countdown.yxmc has an iterative feedback
input/output and an iteration limit.

See [the full CLI guide](../../docs/workflow_cli.md) for graph editing, node
templates, configuration modes, evidence scopes and remaining limitations.
