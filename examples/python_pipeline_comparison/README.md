# Comparing handwritten Python with Phase 2

The synthetic transaction example renames fields, filters posted transactions of at least 100 cents with a region, retains the first eligible row per ID, and aggregates by date and region. It exports a CSV summary, an HTML table and a local `.eml` draft with the summary attached. The fixture exercises a repeated ID with different amounts, missing fields, a declined transaction and a transaction below the threshold.

From the repository root, use the project's Python environment and a fresh output directory.

```powershell
.venv/Scripts/python.exe examples/python_pipeline_comparison/compare.py reports/pipeline-comparison-review
```

To run native probes through CSV, pass `--engine` with the path to `AlteryxEngineCmd.exe`. For a Designer demo, open `designer-report/transaction-report.yxmd`. It has the native Table and Render nodes and writes the synthetic summary and HTML report in its own directory. The full workflow in `baseline/transactions.yxmd` can be inspected in Designer. Use the Python `html-draft-v1` profile to produce its local email draft.

`comparison.json` records the outcomes. `baseline` and `by-product` contain the generated Alteryx workflow, Phase 1 and Phase 2 sources, and outputs from the handwritten reference, both compiler phases and an isolated process running the delivered script. The generated variants compare exact frame data, dtypes, metadata and artifact bytes. The independent reference comparison checks business row and column order, CSV values, HTML table cells and the parsed draft headers, body and attachment.

The change request adds product as a group key and changes the subject. The runner applies literal edits to copies of the original scripts, saves both diffs and independently regenerates Python from an updated workflow. The edit literals document the generator layout reviewed in this experiment. If the generator changes that layout, update the edits to measure the new handoff.

## Observed results

| Check | Result |
| --- | --- |
| Baseline and product grouping | Both matched the independent Python reference at 3 business checkpoints. Each comparison also matched 11 nodes, 12 anchors and 3 output files between generated versions. |
| Change request | Both edited scripts produced the expected product grouping, attachment and subject. Both now change the group key list and the email subject. The original Phase 2 required 4 edits. |
| Source size | 63 nonblank lines and 4 functions in the reference. Phase 2 emits roughly 200 nonblank lines, including encoding, typing, delivery and scalar fallbacks. |
| No eligible transactions | All three versions generate a header-only CSV and empty HTML and email tables. |
| Designer 2025.1 | The full fixture displays all 11 tool icons. The report-only fixture ran and produced CSV rows and HTML table cells matching the standalone Python result. |
| Native EngineCmd 2025.1 | The installed executable returned `engine_license_unavailable` for automated probe collection. |

The runner exits with `1` if the empty-result case differs or a requested native run cannot establish a match. Read the report before interpreting the exit code.

Phase 2 shares the group key list for compatible Summarize → Sort pairs. It uses named pandas aggregation for the supported Count and integer Sum cases and Series predicates for supported string and integer comparisons. It retains scalar fallbacks for other schemas to preserve Phase 1 behavior.
