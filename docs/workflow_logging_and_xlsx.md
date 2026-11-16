# Migrate an After Run logging command

Select the zero-based XML index of the enabled `After Run` command event.
The index follows the source `Properties/Events/Event` order, including
disabled entries. For example, `--log-event 0` selects the first event.
Use this option for a command whose role is logging.

```powershell
$py = '.venv/Scripts/python.exe'
New-Item -ItemType Directory -Force reports/migration | Out-Null
& $py -m alteryx2python.cli run path/to/copy.yxmd --target-node 42 `
    --log-event 0 --workflow-log reports/migration/phase-one.jsonl

& $py -m alteryx2python.cli readable path/to/copy.yxmd --log-event 0 `
    --output reports/migration/phase_two.py
& $py -I reports/migration/phase_two.py --input-dir path/to/inputs `
    --output-dir reports/migration/delivery --workflow-log reports/migration/phase-two.jsonl
```

The selected event uses Python's `alteryx.workflow` logger and emits a JSON
record after success or failure. It includes a run ID, workflow, timestamps,
user, computer, working directory, warning and error counts, and the failure
description when applicable. Conversion errors have their own field and are
`null` until separately counted. In an imported script, configure the logger
with the application's logging handlers. The standalone command supports
`--workflow-log` to append JSON lines to a local file and otherwise logs to
stderr. Existing command events retain their command behavior and allowlist.
Set the optional `ALTERYX_LOG_SERVER` environment variable to label a server
or deployment region in the record.

## Append to a CSV log

Pass `--workflow-log-columns columns.json` alongside `--workflow-log`
to append CSV rows in an explicit column order. The file contains a JSON
array of record field names. For example:

```json
["server", "workflow", "user", "computer_name", "working_dir",
 "error_count", "conversion_error_count", "warning_count"]
```

This is the wrapper's visible field order. Verify the actual shared CSV
header, field order, encoding and append contract with a local copy. The
Python logger leaves existing headers intact and appends data rows. Counts
that are unavailable are empty in CSV. The same options work for the
canonical runner or a standalone script generated with `--log-event`.

## Reproduce file-backed cases

- Dynamic Input supports `ReadList / Path` for CSV and XLSX. It reads distinct
  paths in filename order, as observed in the Designer CSV fixture. Select an Excel sheet by using
  the template selector or a `|||SheetName$` selector on the input path.
  SQL modification, other path actions and unsupported formats fail with
  their configured mode or file format.
- To replay a **Date Time Now** tool, supply the same ISO date to both
  phases with `--as-of 2026-10-13`. If a formula or macro owns date
  generation, bind its date explicitly in the test copy and use the
  same date in Designer. The flag applies to Date Time Now nodes.
- To render Basic reporting tables to XLSX, use `--delivery-profile
  xlsx-table-v1` on `run` and `readable`. Phase One requires
  `--output-dir` alongside the profile. Phase Two takes its output
  directory at execution. Batched Render supports one group field and
  `Prepend` or `ReplacePath` filenames. With `ReplacePath`, the group
  value supplies an XLSX path and the filename is written under the
  chosen output directory. Duplicate filenames fail before writing.
  Chart fragments, page headers and footers, and
  other filename modes require separate templates.
- For a fixed Output Data sink use `--override-output NODE_ID=PATH`.
  An existing workbook sheet selector is retained unless the override
  supplies one. Use a fresh output directory and compare each expected
  workbook against its counterpart.

```powershell
& $py -m alteryx2python.cli compare --mode xlsx `
    --actual reports/migration/delivery/APACreport.xlsx `
    --expected path/to/designer/APACreport.xlsx
```

The workbook comparison checks worksheet order, cell values, cell types
and formula text. Workbook styling and layout require separate evidence.
