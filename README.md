# Alteryx Migration Python

This repository is being structured as a constitution-driven Alteryx-to-Python migration pipeline and support runtime.

Current priorities:

1. preserve Alteryx semantics before optimization
2. enforce a canonical IR between parsing and generation
3. keep tool semantics modular and metadata-driven
4. validate equivalence through tests, trace, and comparison layers
5. make production support, bug fixes, and change requests diagnosable without raw XML spelunking

Canonical package root:

- `alteryx2python/`

Compatibility-only package:

- `alteryx_runtime/`

Current implemented slices:

- Tool catalog with 347 entries, including all 321 unique identifiers in the pinned official tools list; mappings, executable profiles and native equivalence evidence are tracked separately in [the catalog](docs/tools/catalog.md).
- Every catalog tool type has a config parser (dedicated semantic parsers plus a lossless catalog canonical parser) and a runtime registry entry
- Parser extraction for real workflow nodes, edges, anchors, configs, metadata, containers, and unsupported classifications
- Runtime DAG execution from `WorkflowIR`
- Targeted subgraph execution with skipped frontier warnings
- Baseline tools: `TextInput`, `DbFileInput`, `DbFileOutput`, `Select`, `Sort`, `JSONParse`, `Formula`, `Filter`, `RecordID`, `CrossTab`, `DynamicRename`, `Transpose`, `Join`, and `Union`
- Expression subset for the first MIFID branches
- Real MIFID branch fixtures and golden comparison evidence
- Official `Text_Input.yxmd` one-tool workflow golden comparison evidence for node `98`
- Official Basic `01 Combine 2 Spreadsheets Containing Customer Data.yxmd` multi-tool workflow certification against an Alteryx CSV oracle
- Baseline Python generation that rebuilds `WorkflowIR` and delegates to canonical runtime execution
- Support diagnostics for failed runtime nodes, including schema drift, missing anchors/files, unsupported tools, graph context, likely cause, and suggested fix

Current architectural scaffolding introduced:

- IR models and validators
- runtime context, trace, and executor
- tool registry metadata
- comparison layer
- documentation and fixture layout
- migration governance and triage guidance
- Basic/Advanced official sample inventory
- lightweight JSON-first CLI for inspect, run, compare, and certify
- General CLI graph construction/editing, native node templates, question/Action configuration, standard/batch/iterative macro profiles, runnable generated Python with embedded local macros, headless EngineCmd and per-node proof ledgers. The undocumented Designer/Task Scheduler fallback is disabled. See [Workflow CLI](docs/workflow_cli.md).
- Python script generation for single workflows and recursive sample directories
- pipeline support diagnostics documented in `docs/support_diagnostics.md`
- change-request support maps for report/email maintenance surfaces via `support-map` and compact JSON

Important constraint:

- optimizer code exists only as disabled placeholders and is not part of canonical baseline migration

Verification:

- Install the `local`, `parity`, `test`, `nlp` and `notebooks` extras, then run `.venv/Scripts/python.exe -m pytest -q`: 649 passed, 84.12% coverage (80% required), 2026-11-10. Four dependency/numerical warnings remain in the fixtures.
- `uv run python scripts/sweep_all_languages.py` parses all 1,344 official sample workflows across 9 languages with 0 errors and 0 unknown tool nodes
- Parser/registration coverage is independent of semantic acceptance. A registered unavailable adapter must not count as native equivalence.

CLI example:

- `uv run alteryx2python certify "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd" --target-node 23 --override-output 23=E:/tmp/Excel.CustomerProfileOutput.csv --expect tests/fixtures/real_workflows/combine_customer_profile_expected.csv --compare bytes --log E:/tmp/certify.json`
- `uv run alteryx2python generate-samples "D:/Alteryx/Samples/en" --output-dir reports/generated_workflows/all_samples --log reports/generated_workflows/all_samples_manifest.json`
- `uv run alteryx2python support-map "examples/sample_workflows/w1.yxmd" --log E:/tmp/support-map.json`

Roadmap:

- Expand full workflow IO support beyond CSV and current Excel input, especially YXDB and Excel output.
- Add more Alteryx one-tool-at-a-time samples as certification references beyond `Text_Input.yxmd`.
- Broaden expression, Join, Union, and reshape semantics against official golden outputs.
- Expand CLI batch mode for repeated edge-case certification.
- Keep optimized generation separate until baseline evidence exists for the same slice.
