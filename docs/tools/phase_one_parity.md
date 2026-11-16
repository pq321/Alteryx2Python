# Phase One Designer parity

The selected palette includes 95 tools. The screenshot exclusions are Map
Input, Explorer Box, DCM Connection, the Map question, Tree, Apache Spark Code,
API Output, Test, and Throttle. The scope also includes disabled containers,
standard/nested/batch/iterative macros, app questions and Actions, workflow
events, and User/Global variables.

Use a test case matrix with independently observed Designer outputs. Include
each supported configuration, applicable anchors, representative data and
boundary cases, failure outcomes, and the actual artifacts written by sinks.
A match applies to the particular case and captured bytes. Scope or parser
coverage alone provides no execution evidence.

## Repeatable cases

Run from the repository root with the project environment.

```powershell
$py = '.venv/Scripts/python.exe'
$proof = 'reports/parity/new-phase-one'
& $py -m alteryx2python.parity phase-one-scope --samples 'D:/Alteryx/Samples/en' --output "$proof/scope.json"
& $py -m alteryx2python.parity phase-one-plan --samples 'D:/Alteryx/Samples/en' --output-dir "$proof/matrix"
& $py -m alteryx2python.parity samples --container-macro --output-dir "$proof/cases"
& $py -m alteryx2python.parity samples --control-log --output-dir "$proof/control-log-case"
& $py scripts/parity_batch.py plan "$proof/cases" --root "$proof/container-runs"
& $py -m alteryx2python.parity samples --variable-events --output-dir "$proof/event-case"
& $py -m alteryx2python.parity prepare "$proof/event-case/variable-events.yxmd" --allow-event-command "$proof/event-case/record-event.cmd" --output-dir "$proof/variable-events"
```

The nested-container pair has an outside source and Formula, an inside Filter,
and a call to a standard macro with another macro inside it. The enabled path
receives the transformed input and emits `18` at the outer macro boundary.
The disabled path skips the second container, Filter and macro caller. When
enabled, a zero-row output still needs a readable probe.

The event case resolves the workflow-wide constants `User.rate` and
`User.label` and writes a local
marker file before the run, after success and after completion. Preparation
validates the named local command, records its checksum and gives native and
Python executions separate working directories. Artifacts are compared by
relative path and bytes. Designer exposes workflow-wide user constants under
`User.*`. The Python-only `Global.*` extension has separate runtime tests.
Email events require a test delivery adapter.

For a parameterized app, keep the .yxwz and its native Questions and Actions.
Pass the JSON answers to `prepare --answers path.json`, then enter the same
values in the Designer interface. When a container is skipped by runtime
configuration, record its observed members with repeated `--skipped-node ID`
options on `attest`. An enabled node with a missing probe is incomplete.

## Collection and macro replay

For standard workflows on Windows, the desktop runner opens a batch plan in
one Designer session. It clicks Run, records the results, closes its test tab,
and opens the next file through the same window's file picker. Pass
`-DesignerProcessId` to select an existing blank Designer window when there is
more than one candidate. If no Designer window is open, the installed launcher
starts the first case. The report records the PID for each run. The runner
stops if the PID changes, the tab cannot be closed, or an unexpected dialog appears.
One batch at a time can control the Windows session.
It requires PowerShell 7, a Windows desktop session, and the light theme
controls in Designer 2025.1.

```powershell
pwsh -NoProfile -File scripts/designer_click_run.ps1 -Plan "$proof/container-runs/plan.json" -Report "$proof/container-runs/designer-click-report.json"
```

The report lists new outputs and the Designer results screenshot for each run.
Check Designer's reported outcome before attesting. On Designer 2025.1 the
batch can run a prepared app with one integer Numeric Up Down question through
**Options > Run Analytic Apps**, using its default or the value recorded by
`prepare --answers`. Use a timeout that allows for Designer's app startup.
Other interfaces and out-of-range values are listed as pending input. Use a
fresh directory to run a case again.
The runner checks the hashes and document version of macro dependencies before
opening a prepared workflow. Native macro Question definitions start with Tab
elements, with the individual controls nested inside each Tab.

```powershell
& $py -m alteryx2python.parity attest "$proof/variable-events" --status success
& $py -m alteryx2python.parity collect "$proof/variable-events" --manual
& $py scripts/parity_batch.py attest "$proof/container-runs" --outcomes "$proof/outcomes.json" --reviewer 'Designer'
& $py scripts/parity_batch.py collect "$proof/container-runs"
```

The batch outcomes JSON maps run directory names from `plan.json` to objects
such as `{"status":"success"}` or
`{"status":"failed","failed_nodes":["3"]}`. The script reports pending and
nonmatching runs as nonzero during collection.

AMP probe files use a different YXDB format. Prepare a second Designer workflow
to export those probes to classic YXDB without changing the engine of the
original workflow. Keep the original probe files and inspect both runs before
attesting. The review records the raw and classic file hashes.

Control Container logs include file-output records emitted by probes inside the
container. The collector removes only events whose tool ID, message type and
destination identify an injected probe. It preserves those rows in
`excluded_probe_log_rows` in `native.json` and keeps the original YXDB hashes.
The normalized log is also used for comparisons at connected Control inputs.

```powershell
& $py -m alteryx2python.parity prepare-amp-export "$proof/amp-run" | Set-Content "$proof/amp-export-plan.json"
pwsh -NoProfile -File scripts/designer_click_run.ps1 -Plan "$proof/amp-export-plan.json" -Report "$proof/amp-export-report.json"
```

```powershell
& $py -m alteryx2python.parity replay-macro '<attested-enabled-run>' 6 --output-dir "$proof/replay"
```

Replay builds a small workflow from the caller configuration and the upstream
YXDB artifacts, including batch control inputs when present. It compares the
Phase One macro outputs with the original Designer boundary outputs. Check
the replay against the parent run when a macro relies on workflow filenames,
events or other caller context. `python.json` records nested Python captures
under the caller ID and invocation number. Native proof inside a macro body,
or per batch or feedback iteration, still needs additional native probes.

Fixed Output Data destinations are isolated into the run directory. Successful
attestations require the produced file, and behavioral comparison checks the
artifact separately from the input data. Dedicated cases are still needed for
dynamic destination, reporting, external service and advanced format behavior.
