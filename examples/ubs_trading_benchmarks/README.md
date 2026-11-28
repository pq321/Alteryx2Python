# UBS trading benchmarks

Four synthetic financial scenarios cover reconciliation, trade surveillance,
multi-region position risk, and the existing MiFID II workflow. The inputs are
deterministic and the HTTP and SMTP fixtures run on loopback.

From the repository root, use its Python environment to build and run the
benchmarks. The full run requires Windows, Alteryx Designer 2025.1, and PowerShell.
Use a new report directory for each run.

```powershell
python examples/ubs_trading_benchmarks/prepare_datasets.py
python examples/ubs_trading_benchmarks/run_showcase.py --output-dir reports/ubs_benchmark_showcase
```

Pass `--designer-pid` to use a blank Designer session, or pass `--scenario 4`
to run only MiFID. Open the resulting `index.html` for workbooks, HTML reports,
emails, generated source, and Phase 1 checkpoint results.

Replay an existing package with fresh outputs and without Designer. For MiFID,
this command starts a new fixture server and passes its endpoint as configuration.

```powershell
python examples/ubs_trading_benchmarks/run_showcase.py --replay-python reports/ubs_benchmark_showcase/04_mifid_ii_regulatory --output-dir reports/ubs_mifid_replay
```

The original MiFID canvas remains in `examples/sample_workflows`. The staged
copy uses a fixed worksheet, a file-path Action, and a configurable localhost
endpoint. The raw workbooks include the workflow's technical RecordID column.
The comparison and the accompanying 87-column exports use the transaction
reference to align rows and omit a fully empty template row.

The benchmark reports business artifact parity and Phase 1 probe parity
separately. A difference or incomplete result makes the command exit nonzero.
