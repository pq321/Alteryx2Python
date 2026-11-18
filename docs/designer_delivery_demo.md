# End-to-end Designer demo

The demo uses the Record ID workflow installed with Designer. Preparation copies
the sample and adds a CSV sink to grouped Record ID tool 138. The input stays
embedded in the sample. Tool 138 assigns IDs starting at 1 within each Region.

## Run the demo on Windows

From the repo root, use Python 3.11+, PowerShell 7 and the local Designer
installation. Run `python -m venv .venv` and install the project with
`.venv/Scripts/python.exe -m pip install -e ".[parity]"` if needed.
Set the sample path to match your Designer installation. Use a fresh
report directory for each new Designer run.

```powershell
$py = '.venv/Scripts/python.exe'
$root = 'reports/parity/record-id-demo'
$sample = 'D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/02 Preparation/Record_ID.yxmd'
& $py -m alteryx2python.parity prepare-record-id-demo $sample --output-dir $root
pwsh -NoProfile -File scripts/designer_click_run.ps1 -Plan "$root/plan.json" -Report "$root/designer-run.json"
```

The runner starts Designer 2025.1 directly if no matching window is open.
For a custom installation, pass `-DesignerLauncher` with the full path to
the 2025.1 `AlteryxGui.exe`. If multiple Designer 2025.1 processes are open,
give the runner the PID of a blank Designer window with `-DesignerProcessId`.
Reuse that PID for the next invocation. The runner saves a Designer Results
screenshot and closes the workflow tab it opened.

When Results identifies an AMP run, convert its probes in Designer before
attesting. Review both Results screenshots for successful completion and
check the exit code of each command before continuing.

```powershell
& $py -m alteryx2python.parity prepare-amp-export "$root/native" |
    Set-Content "$root/export-plan.json"
pwsh -NoProfile -File scripts/designer_click_run.ps1 -Plan "$root/export-plan.json" -Report "$root/export-run.json"
```

```powershell
& $py -m alteryx2python.parity attest "$root/native" --status success --reviewer 'Designer Results'
& $py -m alteryx2python.parity verify-delivery "$root/native" --output-dir "$root/delivery"
```

After the original Designer run and attestation, reuse those same native
results during a presentation. Run `verify-delivery` with a new delivery
directory to regenerate and execute both Python scripts without opening
Designer again.

For the browser portion, run `& $py -m webapp.server` and open
`http://127.0.0.1:18081`. Import `record-id-demo.yxmd`, click the left
side of Record ID node 138 and inspect the Configuration XML. It shows
`Grouped Record ID`, start value `1`, and group field `Region`.

## Review the result

| File in the delivery directory | What to check |
| --- | --- |
| `acceptance.json` | All three stages report `match`, with source and Python hashes. |
| `native-vs-phase-one.json` | Probe comparisons by node, direction and anchor, including the output from tool 138. |
| `phase-one-vs-phase-two.json` | Generated Phase One and Phase Two checkpoints and output hashes. |
| `phase_one.py`, `phase_two.py` | The two generated programs. Ship `phase_two.py` with its Python dependencies and any workflow input files. |
| `standalone.json`, `delivery-output/grouped-records.csv` | The exit code, hash and bytes from running the shipped Phase Two file in a separate Python process. |

On 2026-11-16, the installed sample produced 6 records across 4 regions in
Designer 2025.1 using AMP. Eight native comparisons matched by value and
order, and all 19 Phase One and Phase Two node checkpoints matched. The
CSV from Designer, both Python builds and standalone execution had the
same SHA-256 hash.

```text
c5147d190762537384357decea1f65105e95427807c613aab362b42e5f6a2be8
```

## Bring a company workflow

Use a copy of an authorized workflow with test inputs and a fixed local
file output. `scripts/parity_batch.py plan <workflow> --root <directory>`
creates a Designer plan for a single workflow with default parameters.
For explicit app answers, use the `prepare --answers` procedure in
[Phase One Designer parity](tools/phase_one_parity.md) and enter those
answers in Designer. The run directory containing `manifest.json` is the
argument to `attest` and `verify-delivery`.

Keep workflow XML, inputs, native probes and generated files on the
authorized workstation. The repository excludes `reports/`. Unsupported
tool configurations, incomplete native evidence and differing outputs
produce a nonzero status. The successful case above covers the specific
sample and inputs under the behavioral profile. Verify each company
workflow using its own inputs and Designer evidence.
## Guided migration

Run the following from the repository root in a terminal. Use a fresh case
directory for each input and answer combination.

```powershell
$py = '.venv/Scripts/python.exe'
& $py -m alteryx2python.cli migrate '.\example.yxwz' --run-dir reports/example-case --interactive --designer auto
```

1. The command writes the node, question, event and audit reports. It stages
   supported local file inputs and the File Browse selections, then records
   the paths and SHA-256 digests in `inputs.json`. Runtime-discovered paths
   and macro dependencies can still require a separate fixture.
2. Press Enter to accept a question's default. Enter dates as `YYYY-MM-DD`.
   `--answers path.json` replays saved answers and omitting both answer
   options uses app defaults. Follow `answers.json` in the Designer dialog.
   The numeric single-question adapter verifies its value automatically.
   For multiple questions, confirm the displayed values and click **Finish**.
   `--designer auto` tries the identifiable magic wand and falls back to
   **Options → Run as Analytic App → External File**. Select `wand` or
   `options` to use a specific route. Use `--designer-pid` for an existing blank
   Designer 2025.1 window. Without `--designer`, open the prepared file
   under `native/` in Designer and run it there.
   To reopen an already prepared case, omit the source workflow and run
   `migrate --run-dir reports/example-case --designer options`.
3. After reviewing the Designer result, resume using the observed outcome.
   Add `--failed-node ID` for a failed run and `--skipped-node ID` for observed
   skips. For AMP probes, use the existing AMP export instructions before
   attestation. A controlled missing-input case can be prepared with
   `--allow-missing-input`. An isolated command event needs an explicit
   `--allow-event-command path` during preparation.
   For an After Run command used only to log the workflow outcome, select its
   original event ID with `--log-event ID` during preparation. Use the ID from
   `events.json`. The prepared Designer copy excludes that command. Phase 1
   and Phase 2 write separate local JSONL logs in the delivery directory.
   `acceptance.json` records whether both Python phases logged the selected
   event IDs with the expected outcome.

   ```powershell
   & $py -m alteryx2python.cli migrate --run-dir reports/example-case --resume --native-outcome success
   ```

4. Read `delivery/acceptance.json`. The native evidence is compared against
   the generated Phase 1 by node and anchor. Phase 2 runs as an independent
   delivered script. The guided comparison checks its exit outcome and
   output file content, plus isolated event files where applicable.
   A successful case needs a declared output to establish delivery parity.
   A repeated resume writes a separate delivery directory.
