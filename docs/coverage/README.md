# Local configuration coverage

The [configuration matrix](tool_configuration_matrix.csv) records individual
cases. The [tool summary](tool_coverage_summary_95.csv) aggregates those cases
over the selected 95 tools. Schema files retain the difference between values
declared by an installed component and values seen in sample XML. An unresolved
domain leaves schema enumeration open.

## Run a fixture

Run the commands from the repository root. A fixture names the XML path to vary,
its baseline/variant pairs, and a data archetype. The same canvas contains all
variants. The check also builds four boundary datasets and applies the Classic
and AMP requirements for that tool.

```powershell
.venv/Scripts/python.exe -m alteryx2python.parity check-tool RecordID --work-dir reports/record-id-coverage
.venv/Scripts/python.exe -m alteryx2python.parity verify-tool RecordID --work-dir reports/record-id-coverage --designer-pid <PID>
.venv/Scripts/python.exe -m alteryx2python.parity update-ledger
```

Use `--cases tests/fixtures/tool_matrix/DbFileInput/xlsx.json` to select the
Excel input cases. Use `verify-tool --native-runs <directory>` to recompare
unchanged, attested Designer probes after a Python fix. The receipt covers the
examined case IDs and uses the original Designer evidence. The ledger loader
checks the source, fixture inputs, package files, receipts, and probe hashes.
The committed ledger contains the portable case definitions. Run verification locally to populate it with machine-specific receipts.

## Refresh the schema inventory

```powershell
.venv/Scripts/python.exe -m alteryx2python.parity schema-sync --alteryx-dir D:/Alteryx
```

Use `--historical-csv <path>` to rebuild the ledger from the schema files and the
historical case definitions. Run `update-ledger` to apply local verification
receipts. The schema command returns a nonzero exit code while any domains
remain unresolved. The case ledger records only the verified parts of the
configured fixtures.
