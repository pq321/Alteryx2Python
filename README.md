# Alteryx Migration Python

This repository is being structured as a constitution-driven Alteryx-to-Python migration framework.

Current priorities:

1. preserve Alteryx semantics before optimization
2. enforce a canonical IR between parsing and generation
3. keep tool semantics modular and metadata-driven
4. validate equivalence through tests, trace, and comparison layers

Canonical package root:

- `alteryx2python/`

Compatibility-only package:

- `alteryx_runtime/`

Current implemented slices:

- Parser extraction for real workflow nodes, edges, anchors, configs, metadata, containers, and unsupported classifications
- Runtime DAG execution from `WorkflowIR`
- Targeted subgraph execution with skipped frontier warnings
- Baseline tools: `TextInput`, `DbFileInput`, `DbFileOutput`, `Select`, `Sort`, `JSONParse`, `Formula`, `Filter`, `RecordID`, `CrossTab`, `DynamicRename`, `Transpose`, `Join`, and `Union`
- Expression subset for the first MIFID branches
- Real MIFID branch fixtures and golden comparison evidence
- Official `Text_Input.yxmd` one-tool workflow golden comparison evidence for node `98`
- Official Basic `01 Combine 2 Spreadsheets Containing Customer Data.yxmd` multi-tool workflow certification against an Alteryx CSV oracle
- Baseline Python generation that rebuilds `WorkflowIR` and delegates to canonical runtime execution

Current architectural scaffolding introduced:

- IR models and validators
- runtime context, trace, and executor
- tool registry metadata
- comparison layer
- documentation and fixture layout
- migration governance and triage guidance
- Basic/Advanced official sample inventory
- lightweight JSON-first CLI for inspect, run, compare, and certify

Important constraint:

- optimizer code exists only as disabled placeholders and is not part of canonical baseline migration

Verification:

- `uv run python -m pytest -q`

CLI example:

- `uv run alteryx2python certify "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd" --target-node 23 --override-output 23=E:/tmp/Excel.CustomerProfileOutput.csv --expect tests/fixtures/real_workflows/combine_customer_profile_expected.csv --compare bytes --log E:/tmp/certify.json`

Roadmap:

- Expand full workflow IO support beyond CSV and current Excel input, especially YXDB and Excel output.
- Add more Alteryx one-tool-at-a-time samples as certification references beyond `Text_Input.yxmd`.
- Broaden expression, Join, Union, and reshape semantics against official golden outputs.
- Expand CLI batch mode for repeated edge-case certification.
- Keep optimized generation separate until baseline evidence exists for the same slice.
