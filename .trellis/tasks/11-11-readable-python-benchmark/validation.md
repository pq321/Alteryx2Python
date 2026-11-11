# Validation - November 11, 2026

## Framework v2 acceptance

The user's readability correction applies to the compiler, not one output.
The previous standalone result was not accepted as sufficiently readable.

- Native configuration-specific IO/tabular/relational/reshape/field templates,
  bounded AST specialization, lexical-safe linking, stage assembly and pruning.
- Delivered code presents orchestration first and excludes checkpoint plumbing.
  A separate verification build uses the same operation AST.
- 407 additional tests cover unrelated fields/configurations/topologies, file
  formats, nulls, grouped/empty data, ordering, closures, comprehensions, defaults,
  exception aliases, symbol collisions and semantic provenance. No sample-output
  patches or model-based intent inference are involved.
- Final complete suite: 1126 passed, four existing dependency/numerical warnings,
  85.90% coverage. Command: .venv/Scripts/python.exe -m pytest -q
  -o addopts=--cov=alteryx2python
  --cov-report=json:reports/readable-dev/framework-coverage-final.json.
- Connected benchmark: 38 outer nodes agree exactly in values, dtypes, order and
  field metadata; all eight files agree. The shipped and instrumented programs
  execute separately. Isolated standalone execution and changed parameters pass.
- The checked-in example was regenerated only through the framework. Existing
  script hashes, baseline source and all output hashes were checked before the
  generated code/manifest/IR/acceptance report were refreshed. No human edits
  were overwritten, and all real output files remain byte-identical.
- Review findings were repaired in the compiler and regression-tested. A
  pre-existing Union validator now respects configured connection ordering.
- Source compilation and whitespace checks pass. No dependencies were added.
- The delivery gate rejects leftover configuration/anchor/capture machinery;
  decimal local contexts remain valid native Python. Generator tests: 428 passed.
  Final benchmark evidence: reports/readable-dev/framework-v2-final-gate/.

The initial evidence below is historical; official full-tool and native coverage
remain open. Keep the task in progress.

## Implemented

- Deterministic Phase Two compiler, strict Phase One AST reader, template source
  linker, expression lowering, compiler/helper/config hashes and editable output.
- Numeric user parameters; static and ordered-output macro expansion, including
  embedded sources and nested container ownership.
- Workflow before/after, success/failure/warning events and actual Windows batch
  execution; explicit allowlists and working-directory overrides for proof runs.
- Select/Formula type and size contracts; string truncation, integer bounds,
  decimal scale and declared Field Info metadata.
- Real command execution and HTML/email-draft profile, keeping legacy defaults.
- Missing Generate Rows, multi-field and multi-row expression templates, helper
  classes/regex constants, CrossTab aggregation and Append Fields configuration.
- CLI commands, public Iris data/provenance, connected app and all-tool inventory.

## Evidence

- Full regression: 719 passed, 4 dependency/numerical warnings, 85.03% coverage
  against the required 80%. Command: .venv/Scripts/python.exe -m pytest -q
  --cov-report= --cov-report=json:reports/readable-dev/final-coverage.json.
- Source syntax compilation and git diff whitespace checks passed.
- examples/readable_benchmark/acceptance/acceptance.json: 38 outer nodes with
  exact dataframe/dtype/schema agreement; 8 real output files byte-identical.
- Copied standalone script executes with isolated Python and a module finder
  rejecting both project package names. No repository imports are needed.
- One compiled script accepts 5, 6.5 and 7 as changed numeric answers and matches
  independently rebound baseline executions.
- Actual event tests cover success/failure/warnings, configured working dirs,
  quoted paths/backslashes and a batch filename containing spaces.
- Embedded macro tests remove the original macro file and verify enabled and
  disabled nested containers using only the preserved snapshot.
- Inventory scans 208 installed English workflows with zero parser errors;
  retains all 323 official rows, 147 configured sample rows, 98 source-linking
  probe compilations, 34 official rows covered by the connected differential.
  Probe compilation is not execution coverage. Inventory returns nonzero.
- Native EngineCmd 2025.1.2.165 probe is blocked: The Feature "API or
  FlowChartMode" is not licensed. Source/result remain under
  reports/readable-dev/native-probe1; result copied to the example directory.

## Open Acceptance Criteria

The entire official-tool requirement is not complete. Missing native fixtures,
external integrations and licensed data/model adapters, additional report
formats/configurations, dynamic macro lowering and additional user-question
types remain explicit blockers. Native equivalence is unverified. Keep this task
in progress; do not archive it or describe registration/probes as full coverage.

No dependencies were added. No emails were sent. No Designer GUI or scheduled
task was started. Generated code remains uncommitted for review.
