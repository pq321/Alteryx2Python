# Alteryx2Python Long-Range Execution Checklist

## How To Use This Checklist

- Treat this file as the canonical execution backlog for the repository.
- Work top to bottom unless a milestone explicitly says parallel work is safe.
- Do not start a later milestone until the current milestone exit criteria are met.
- Preserve the constitutional rule: correctness before elegance, tool boundaries before optimization.
- Keep diffs small. Prefer one sub-checklist item per PR or per focused work session.

## Current Status Snapshot

- [x] Canonical package root exists under `alteryx2python/`.
- [x] Runtime trace/context skeleton exists.
- [x] Tool registry skeleton exists.
- [x] Initial IR models and validators exist.
- [x] `Select` first slice is implemented and documented.
- [x] Basic `Select` and runtime tests exist under `tests/`.
- [ ] Parser can extract real nodes/edges/config from a real workflow file.
- [ ] Runtime can execute a graph from IR.
- [ ] Generator can emit runnable workflow Python from IR.
- [ ] Real workflow fixtures and golden outputs are checked in and tested.
- [ ] Certification-grade workflow comparison loop exists.

## Global Rules For Every Milestone

- [ ] Add or update tests before claiming a milestone is complete.
- [ ] Update docs when behavior or scope changes.
- [ ] Record unsupported behavior explicitly instead of approximating it.
- [ ] Keep optimizer code disabled unless a milestone explicitly enables a certified optimized layer.
- [ ] Run verification commands and read the output before marking checklist items done.

## M0 - Preserve And Stabilize The Existing Select Slice

### Goal

Lock the current `Select` slice as the known-good baseline that later milestones can build on.

### In Scope

- Existing `Select` semantics
- Existing runtime trace behavior
- Existing schema snapshot and schema diff behavior
- Existing registry wiring

### Task Checklist

- [x] Keep `alteryx2python/tools/select.py` as the canonical baseline implementation.
- [x] Keep `alteryx2python/runtime/context.py` and `alteryx2python/runtime/trace.py` as the baseline trace contract.
- [x] Keep `alteryx2python/comparison/schema_diff.py` as the baseline schema comparison contract.
- [x] Keep `tests/test_tools/test_select.py` passing.
- [x] Keep `tests/test_tools/test_select_failures.py` passing.
- [x] Keep `tests/test_tools/test_registry.py` passing.
- [x] Keep `tests/test_runtime/test_executor.py` passing.
- [ ] Replace environment-specific verification notes with a stable repo verification recipe once package download issues are resolved.

### Exit Criteria

- [ ] The project can run the current baseline tests in a reproducible environment.
- [ ] The repo has one documented command sequence for baseline verification.

## M1 - Real Workflow Fixture Intake

### Goal

Bring one real Alteryx workflow into the repo as the primary parser and execution target.

### Initial Target

- `examples/sample_workflows/MIFID II.yxwz` on `origin/main`

### Why This Comes First

The project now has abstractions but no grounded end-to-end target. This milestone prevents building parser/runtime/tool semantics against imaginary workflows.

### Task Checklist

- [x] Add the real sample workflow directory to the local branch if it is not already present in the working tree.
- [x] Create a local fixture strategy under `tests/fixtures/real_workflows/`.
- [x] Decide and document whether raw `.yxwz` examples are committed directly, copied into fixtures, or referenced from `examples/`.
- [x] Add a workflow inventory note to docs describing:
  - node count
  - connection count
  - plugin/tool types present
  - external file dependencies
  - expected unsupported node categories
- [x] Add a parser-facing smoke test that only proves the sample workflow XML loads successfully.
- [x] Add a fixture README that explains what is real, what is synthetic, and what is sanitized.

### Files To Touch

- `examples/` or `tests/fixtures/real_workflows/`
- `tests/fixtures/README.md`
- `docs/architecture.md`
- `tests/test_parser/` (new)

### Exit Criteria

- [x] One real workflow file is present and documented in the repo.
- [x] A test proves the workflow file can be loaded as XML without hand-editing.
- [ ] The repo documents the workflow's external dependency surface.

## M2 - XML Parser To Canonical IR

### Goal

Upgrade the parser from workflow-shell parsing to real node/edge/config extraction.

### Required Parser Outputs

- Workflow metadata
- Node list
- Edge list
- Tool/plugin identity
- Anchor names when available
- Raw configuration payloads
- MetaInfo snapshots when available
- Container membership and child-node relationships
- Warning/error classification for unsupported nodes

### Task Checklist

- [x] Expand `alteryx2python/parser/xml_parser.py` to parse `<Nodes>` and `<Connections>`.
- [x] Map Alteryx `ToolID` to `NodeIR.node_id` and preserve original source tool ID.
- [x] Parse plugin strings from `<GuiSettings Plugin="...">`.
- [x] Capture raw node configuration into `NodeIR.config`.
- [x] Extract input/output anchor details where the XML exposes them.
- [x] Extract `MetaInfo/RecordInfo/Field` metadata into a schema-friendly structure.
- [x] Parse `ChildNodes` under tool containers.
- [x] Detect non-executable UI-only nodes and classify them separately.
- [x] Detect action/interface-style nodes and record them as unsupported or deferred.
- [x] Populate `WorkflowIR.warnings` and `NodeIR.supported_status` instead of silently dropping unknown structures.
- [x] Add parser contract tests for:
  - minimal workflow shell
  - workflow with connections
  - workflow with tool container children
  - workflow with `MetaInfo`
  - workflow with unsupported plugin types
- [x] Add a snapshot-style test against the real sample workflow that checks node/edge counts and key plugin types.

### Files To Touch

- `alteryx2python/parser/xml_parser.py`
- `alteryx2python/parser/base_parser.py`
- `alteryx2python/ir/models.py`
- `alteryx2python/ir/schema.py`
- `alteryx2python/ir/validators.py`
- `tests/test_parser/` (new)
- `docs/ir.md`

### Exit Criteria

- [x] The real workflow parses into a populated `WorkflowIR`.
- [x] IR validation passes on the real workflow or fails only for explicitly documented unsupported reasons.
- [x] Parser tests cover both synthetic XML and the real sample workflow.

Note: `M2` stops at raw XML-to-IR extraction. Tool-specific config normalization remains part of `M3`.

## M3 - Tool Mapping Layer And Parser Specialization

### Goal

Create a clean boundary between raw XML parsing and tool-specific semantic parsing.

### Task Checklist

- [x] Define a plugin-to-tool-type normalization strategy.
- [x] Introduce parser dispatch from XML parser to tool-specific parsers.
- [x] Keep `Select` as the first fully parsed tool config.
- [x] Add new parser modules for the first execution tools:
  - `DbFileInput`
  - `Formula`
  - `Filter`
  - `Join`
  - `Union`
  - `Transpose`
  - `RecordID`
- [x] Decide what fields belong in normalized config versus preserved raw config.
- [x] Ensure every tool parser can emit warnings when it only partially understands a config.
- [ ] Document the plugin mapping table in docs.

### Files To Touch

- `alteryx2python/parser/tool_parsers/`
- `alteryx2python/parser/xml_parser.py`
- `alteryx2python/tools/registry.py`
- `docs/architecture.md`
- `docs/tools/` (new files)
- `tests/test_parser/`

### Exit Criteria

- [x] XML parser no longer hardcodes tool understanding in one place.
- [x] At least `Select` plus one additional execution tool have dedicated config parsers.
- [x] Tool parser tests prove normalized config output shape.

## M4 - Expression Engine Foundation

### Goal

Make formula and filter work on a controlled Alteryx-like expression layer instead of ad hoc pandas logic.

### Task Checklist

- [ ] Audit the existing files under `alteryx2python/expressions/` for completeness versus placeholders.
- [ ] Define the minimum supported expression subset needed for the first real workflow branch.
- [ ] Add parser/evaluator tests for:
  - field references
  - string literals
  - numeric literals
  - boolean expressions
  - null-aware behavior
  - `StartsWith`
  - `REGEX_Replace`
- [ ] Implement explicit unsupported-function errors for everything outside the initial subset.
- [ ] Document Alteryx-vs-Python semantic differences for the supported subset.

### Files To Touch

- `alteryx2python/expressions/ast.py`
- `alteryx2python/expressions/parser.py`
- `alteryx2python/expressions/evaluator.py`
- `alteryx2python/expressions/functions.py`
- `tests/test_expressions/` (new)
- `docs/` expression semantics doc (new or folded into architecture)

### Exit Criteria

- [ ] The expression layer can support the first real `Formula` and `Filter` nodes needed by the sample workflow.
- [ ] Unsupported expression features fail explicitly.

## M5 - Core Tool Semantics For First Real Subgraph

### Goal

Implement just enough tools to run one meaningful subgraph from the sample workflow.

### Recommended First Tool Set

- `DbFileInput`
- `Select`
- `JSONParse`
- `Formula`
- `Filter`

### Why This Set

The real sample workflow starts with this sequence and it is the shortest path to proving the architecture works on actual Alteryx structure.

### Task Checklist

- [ ] Implement `DbFileInput` baseline semantics with explicit limits on supported file types and options.
- [ ] Expand `Select` only if real workflow configs expose missing semantics.
- [ ] Implement `JSONParse` baseline semantics for the observed configuration shape.
- [ ] Implement `Formula` baseline semantics backed by the controlled expression engine.
- [ ] Implement `Filter` baseline semantics with true/false anchor outputs.
- [ ] Register each tool in `alteryx2python/tools/registry.py`.
- [ ] Add tool docs under `docs/tools/`.
- [ ] Add success and failure tests for each tool.
- [ ] Add tests for row order, row count, anchor shape, and schema shape.

### Files To Touch

- `alteryx2python/tools/`
- `alteryx2python/tools/registry.py`
- `tests/test_tools/`
- `docs/tools/`

### Exit Criteria

- [ ] The first real subgraph tools are implemented, registered, and tested.
- [ ] Each tool has an explicit list of supported and deferred semantics.

## M6 - DAG Runtime Execution From IR

### Goal

Execute a parsed workflow graph from IR rather than invoking isolated tools manually.

### Task Checklist

- [ ] Extend `alteryx2python/runtime/executor.py` from single-node helper to graph executor.
- [ ] Add topological ordering based on `WorkflowIR.edges`.
- [ ] Add anchor-aware input routing between nodes.
- [ ] Preserve multi-output anchor behavior.
- [ ] Decide how to store intermediate node outputs in memory.
- [ ] Propagate node failures with enough context for debugging.
- [ ] Distinguish fatal errors from workflow warnings.
- [ ] Add executor tests for:
  - linear pipeline
  - branching outputs
  - missing upstream anchor
  - unsupported tool stop
  - node trace accumulation order

### Files To Touch

- `alteryx2python/runtime/executor.py`
- `alteryx2python/runtime/context.py`
- `alteryx2python/runtime/node_result.py`
- `alteryx2python/runtime/trace.py`
- `tests/test_runtime/`
- `docs/architecture.md`

### Exit Criteria

- [ ] A small synthetic `WorkflowIR` graph can execute end-to-end.
- [ ] Runtime traces show node order, inputs, outputs, warnings, and errors.

## M7 - First Real Workflow Subgraph Execution

### Goal

Run a real parsed portion of `MIFID II.yxwz` through the canonical runtime.

### Recommended Initial Target

- `DbFileInput -> Select -> JSONParse -> Formula -> Filter`

### Task Checklist

- [ ] Build a fixture input dataset for the first real subgraph.
- [ ] Add a focused integration test that parses the workflow and executes only the supported node chain.
- [ ] Add a mechanism to select a subgraph or stop execution at unsupported nodes.
- [ ] Capture output schema and output rows for the supported subgraph.
- [ ] Record explicit warnings for skipped nodes beyond the supported frontier.

### Files To Touch

- `tests/test_integration/` (new)
- `tests/fixtures/real_workflows/`
- `alteryx2python/runtime/`
- `alteryx2python/parser/`
- `docs/testing_strategy.md`

### Exit Criteria

- [ ] One real subgraph from the sample workflow executes through parser -> IR -> runtime.
- [ ] The integration test is stable and reproducible.

## M8 - Tabular Reshaping Tool Family

### Goal

Support the next cluster of tools needed by the sample workflow's middle section.

### Tool Set

- `CrossTab`
- `DynamicRename`
- `Transpose`
- `RecordID`
- `Union`
- `Join`

### Task Checklist

- [ ] Parse configs for each reshaping/join tool.
- [ ] Implement baseline semantics for observed sample-workflow usage first.
- [ ] Add isolated tool tests.
- [ ] Add integration tests for a real multi-tool branch using these tools.
- [ ] Document edge cases that remain unsupported.

### Exit Criteria

- [ ] The sample workflow's central transformation branch is largely executable.
- [ ] Join/union/reshape behavior is verified at tool and integration level.

## M9 - File IO And Output Certification Inputs

### Goal

Handle enough file IO to compare real outputs and support repeatable workflow tests.

### Task Checklist

- [ ] Implement baseline output tool semantics for the observed sample workflow.
- [ ] Decide on repo-safe fixture formats for workflow input/output data.
- [ ] Add helper utilities for loading fixture data and expected outputs.
- [ ] Add a repeatable test harness that can compare produced outputs with golden outputs.

### Files To Touch

- `alteryx2python/tools/`
- `alteryx2python/comparison/`
- `alteryx2python/utils/`
- `tests/fixtures/`
- `tests/test_integration/`
- `docs/certification.md`

### Exit Criteria

- [ ] The repo can run at least one workflow branch and compare produced output with expected evidence.

## M10 - Comparison And Certification Layer

### Goal

Turn execution into evidence, not just successful code paths.

### Task Checklist

- [ ] Expand `alteryx2python/comparison/dataframe_diff.py` beyond placeholder status if needed.
- [ ] Define the canonical comparison report format.
- [ ] Compare:
  - row count
  - column order
  - dtypes
  - cell-level differences
  - null differences
  - ordering differences
- [ ] Add machine-readable comparison output and human-readable summary output.
- [ ] Add report generation tests.
- [ ] Update certification docs with required evidence for a workflow slice.

### Files To Touch

- `alteryx2python/comparison/`
- `docs/certification.md`
- `tests/test_comparison/` (new)

### Exit Criteria

- [ ] Every integration run can emit comparison evidence.
- [ ] Certification docs describe exactly what qualifies as baseline-equivalent for a workflow slice.

## M11 - Generator From Validated IR

### Goal

Generate runnable Python from a validated workflow IR after runtime semantics exist.

### Task Checklist

- [ ] Redesign `alteryx2python/generator/python_generator.py` so it emits executable node-by-node code.
- [ ] Keep generation aligned with canonical tool boundaries.
- [ ] Decide whether generated code calls registered tool functions directly or emits inlined wrappers.
- [ ] Add generator tests for:
  - imports
  - node ordering
  - anchor variable naming
  - config embedding
  - execution-report return shape
- [ ] Add a round-trip test: parse -> generate -> execute generated code -> compare outputs.

### Exit Criteria

- [ ] The generator emits runnable baseline code for at least one supported workflow slice.
- [ ] Generated code stays traceable to original node IDs.

## M12 - Unsupported Features, Governance, And Scale-Out

### Goal

Make the system safe to extend without losing rigor.

### Task Checklist

- [ ] Formalize unsupported classifications in one shared module or doc.
- [ ] Add repo-level workflow triage guidance:
  - safe to auto-migrate
  - partial migration only
  - owner review required
  - custom code required
- [ ] Add a process for introducing a new tool:
  - parser contract
  - tool semantics doc
  - isolated tests
  - integration target
  - certification notes
- [ ] Decide when optimizer work may begin and what certification gate it must pass.
- [ ] Add a project roadmap section to `README.md`.

### Exit Criteria

- [ ] A future agent can add a new tool or workflow slice without rediscovering process.
- [ ] Governance around unsupported behavior is explicit and enforceable.

## Future Optional Milestones

- [ ] Additional real workflow samples beyond `MIFID II`
- [ ] Macro handling
- [ ] Interface/action node support
- [ ] Better type-system emulation
- [ ] Optimized non-canonical generation path
- [ ] CLI for parse/execute/compare workflows

## Verification Log Template

Use this format when finishing any sub-checklist item:

- Item:
- Files changed:
- Tests run:
- Result:
- Known gaps:
