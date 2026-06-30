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
- [x] Parser can extract real nodes/edges/config from a real workflow file.
- [x] Runtime can execute a graph from IR.
- [x] Generator can emit runnable workflow Python from IR.
- [x] Real workflow fixtures for the first executable subgraph are checked in and tested.
- [x] Certification-grade workflow comparison loop exists.
- [x] First complete official one-tool workflow data-output certification exists for `Text_Input.yxmd` target `98`.
- [x] First complete official multi-tool Basic workflow certification exists for `01 Combine 2 Spreadsheets Containing Customer Data.yxmd`.
- [x] Lightweight JSON-first CLI exists for inspect, run, compare, and certify.

## Global Rules For Every Milestone

- [x] Add or update tests before claiming a milestone is complete.
- [x] Update docs when behavior or scope changes.
- [x] Record unsupported behavior explicitly instead of approximating it.
- [x] Keep optimizer code disabled unless a milestone explicitly enables a certified optimized layer.
- [x] Run verification commands and read the output before marking checklist items done.

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
- [x] Replace environment-specific verification notes with a stable repo verification recipe once package download issues are resolved.

### Exit Criteria

- [x] The project can run the current baseline tests in a reproducible environment.
- [x] The repo has one documented command sequence for baseline verification.

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
- [x] The repo documents the workflow's external dependency surface.

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
- [x] Document the plugin mapping table in docs.

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

- [x] Audit the existing files under `alteryx2python/expressions/` for completeness versus placeholders.
- [x] Define the minimum supported expression subset needed for the first real workflow branch.
- [x] Add parser/evaluator tests for:
  - field references
  - string literals
  - numeric literals
  - boolean expressions
  - null-aware behavior
  - `StartsWith`
  - `REGEX_Replace`
- [x] Implement explicit unsupported-function errors for everything outside the initial subset.
- [x] Document Alteryx-vs-Python semantic differences for the supported subset.

### Files To Touch

- `alteryx2python/expressions/ast.py`
- `alteryx2python/expressions/parser.py`
- `alteryx2python/expressions/evaluator.py`
- `alteryx2python/expressions/functions.py`
- `tests/test_expressions/` (new)
- `docs/` expression semantics doc (new or folded into architecture)

### Exit Criteria

- [x] The expression layer can support the first real `Formula` and `Filter` nodes needed by the sample workflow.
- [x] Unsupported expression features fail explicitly.

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

- [x] Implement `DbFileInput` baseline semantics with explicit limits on supported file types and options.
- [x] Expand `Select` only if real workflow configs expose missing semantics.
- [x] Implement `JSONParse` baseline semantics for the observed configuration shape.
- [x] Implement `Formula` baseline semantics backed by the controlled expression engine.
- [x] Implement `Filter` baseline semantics with true/false anchor outputs.
- [x] Register each tool in `alteryx2python/tools/registry.py`.
- [x] Add tool docs under `docs/tools/`.
- [x] Add success and failure tests for each tool.
- [x] Add tests for row order, row count, anchor shape, and schema shape.

### Files To Touch

- `alteryx2python/tools/`
- `alteryx2python/tools/registry.py`
- `tests/test_tools/`
- `docs/tools/`

### Exit Criteria

- [x] The first real subgraph tools are implemented, registered, and tested.
- [x] Each tool has an explicit list of supported and deferred semantics.

## M6 - DAG Runtime Execution From IR

### Goal

Execute a parsed workflow graph from IR rather than invoking isolated tools manually.

### Task Checklist

- [x] Extend `alteryx2python/runtime/executor.py` from single-node helper to graph executor.
- [x] Add topological ordering based on `WorkflowIR.edges`.
- [x] Add anchor-aware input routing between nodes.
- [x] Preserve multi-output anchor behavior.
- [x] Decide how to store intermediate node outputs in memory.
- [x] Propagate node failures with enough context for debugging.
- [x] Distinguish fatal errors from workflow warnings.
- [x] Add executor tests for:
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

- [x] A small synthetic `WorkflowIR` graph can execute end-to-end.
- [x] Runtime traces show node order, inputs, outputs, warnings, and errors.

## M7 - First Real Workflow Subgraph Execution

### Goal

Run a real parsed portion of `MIFID II.yxwz` through the canonical runtime.

### Recommended Initial Target

- `DbFileInput -> Select -> JSONParse -> Formula -> Filter`

### Task Checklist

- [x] Build a fixture input dataset for the first real subgraph.
- [x] Add a focused integration test that parses the workflow and executes only the supported node chain.
- [x] Add a mechanism to select a subgraph or stop execution at unsupported nodes.
- [x] Capture output schema and output rows for the supported subgraph.
- [x] Record explicit warnings for skipped nodes beyond the supported frontier.

### Files To Touch

- `tests/test_integration/` (new)
- `tests/fixtures/real_workflows/`
- `alteryx2python/runtime/`
- `alteryx2python/parser/`
- `docs/testing_strategy.md`

### Exit Criteria

- [x] One real subgraph from the sample workflow executes through parser -> IR -> runtime.
- [x] The integration test is stable and reproducible.

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

- [x] Parse configs for each reshaping/join tool.
- [x] Implement baseline semantics for observed sample-workflow usage first.
- [x] Add isolated tool tests.
- [x] Add integration tests for a real multi-tool branch using these tools.
- [x] Document edge cases that remain unsupported.

### Exit Criteria

- [x] The sample workflow's central transformation branch is largely executable.
- [x] Join/union/reshape behavior is verified at tool and integration level.

## M9 - File IO And Output Certification Inputs

### Goal

Handle enough file IO to compare real outputs and support repeatable workflow tests.

### Task Checklist

- [x] Implement baseline output tool semantics for the observed sample workflow.
- [x] Decide on repo-safe fixture formats for workflow input/output data.
- [x] Add helper utilities for loading fixture data and expected outputs.
- [x] Add a repeatable test harness that can compare produced outputs with golden outputs.

### Files To Touch

- `alteryx2python/tools/`
- `alteryx2python/comparison/`
- `alteryx2python/utils/`
- `tests/fixtures/`
- `tests/test_integration/`
- `docs/certification.md`

### Exit Criteria

- [x] The repo can run at least one workflow branch and compare produced output with expected evidence.

## M10 - Comparison And Certification Layer

### Goal

Turn execution into evidence, not just successful code paths.

### Task Checklist

- [x] Expand `alteryx2python/comparison/dataframe_diff.py` beyond placeholder status if needed.
- [x] Define the canonical comparison report format.
- [x] Compare:
  - row count
  - column order
  - dtypes
  - cell-level differences
  - null differences
  - ordering differences
- [x] Add machine-readable comparison output and human-readable summary output.
- [x] Add report generation tests.
- [x] Update certification docs with required evidence for a workflow slice.

### Files To Touch

- `alteryx2python/comparison/`
- `docs/certification.md`
- `tests/test_comparison/` (new)

### Exit Criteria

- [x] Every integration run can emit comparison evidence.
- [x] Certification docs describe exactly what qualifies as baseline-equivalent for a workflow slice.

## M11 - Generator From Validated IR

### Goal

Generate runnable Python from a validated workflow IR after runtime semantics exist.

### Task Checklist

- [x] Redesign `alteryx2python/generator/python_generator.py` so it emits executable node-by-node code.
- [x] Keep generation aligned with canonical tool boundaries.
- [x] Decide whether generated code calls registered tool functions directly or emits inlined wrappers.
- [x] Add generator tests for:
  - imports
  - node ordering
  - anchor variable naming
  - config embedding
  - execution-report return shape
- [x] Add a round-trip test: parse -> generate -> execute generated code -> compare outputs.

### Exit Criteria

- [x] The generator emits runnable baseline code for at least one supported workflow slice.
- [x] Generated code stays traceable to original node IDs.

## M12 - Unsupported Features, Governance, And Scale-Out

### Goal

Make the system safe to extend without losing rigor.

### Task Checklist

- [x] Formalize unsupported classifications in one shared module or doc.
- [x] Add repo-level workflow triage guidance:
  - safe to auto-migrate
  - partial migration only
  - owner review required
  - custom code required
- [x] Add a process for introducing a new tool:
  - parser contract
  - tool semantics doc
  - isolated tests
  - integration target
  - certification notes
- [x] Decide when optimizer work may begin and what certification gate it must pass.
- [x] Add a project roadmap section to `README.md`.

### Exit Criteria

- [x] A future agent can add a new tool or workflow slice without rediscovering process.
- [x] Governance around unsupported behavior is explicit and enforceable.

## Future Optional Milestones

- [x] M13 - First complete official one-tool workflow certification
- [x] M14 - First complete official multi-tool Basic workflow certification
- [ ] Additional real workflow samples beyond `MIFID II`
- [ ] Macro handling
- [ ] Interface/action node support
- [ ] Better type-system emulation
- [ ] Optimized non-canonical generation path
- [ ] Batch CLI suite files for repeated parse/execute/compare runs
- [x] M15 - Lightweight CLI for repeatable certification
- [x] M16 - Node-level tool contracts and evidence
- [x] M17 - Topology-preserving compact workflow JSON

## M13 - First Complete Official One-Tool Workflow Certification

### Goal

Prove at least one official Alteryx sample workflow can be parsed, executed, generated, and compared against a golden output without replacing external dependencies.

### Target

- `D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/01 In Out/Text_Input.yxmd`
- executable target node: `98`

### Task Checklist

- [x] Inspect the official sample XML and identify the executable data node.
- [x] Implement `TextInput` config parsing for fields, rows, row count, and empty cells.
- [x] Implement `TextInput` runtime semantics with one `Output` anchor.
- [x] Register `TextInput` in the tool registry and package exports.
- [x] Add parser, tool, registry, integration, and generator roundtrip tests.
- [x] Add `tests/fixtures/real_workflows/text_input_expected.csv`.
- [x] Compare parsed runtime output to the golden CSV.
- [x] Compare generated-code runtime output to the golden CSV.
- [x] Document `TextInput` semantics and deferred type-system behavior.
- [x] Update certification and testing strategy docs.

### Exit Criteria

- [x] The official sample parses without hand editing.
- [x] Target node `98` executes through parser -> IR -> runtime.
- [x] Generated Python executes the same target node through the canonical runtime.
- [x] Output rows, column order, and cell values match the golden fixture.

### Known Gaps

- [ ] This certifies the embedded data-output sample only, not arbitrary Alteryx workflows.
- [ ] Full Alteryx Text Input type inference and Results metadata behavior remain deferred.
- [ ] Documentation-only `TextBox` nodes are skipped by target selection rather than modeled as no-op workflow nodes.

## M14 - First Complete Official Multi-Tool Basic Workflow Certification

### Goal

Prove an official multi-tool Alteryx workflow can be parsed, executed, generated, and compared 1:1 against an Alteryx output oracle.

### Target

- `D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd`
- output node: `23`

### Task Checklist

- [x] Inventory Basic/Advanced workflows and tool types.
- [x] Identify Basic `01 Combine 2 Spreadsheets...` as the next certification target.
- [x] Add `openpyxl` for real `.xlsx` input support.
- [x] Preserve workflow-relative file resolution through parser-provided `base_dir`.
- [x] Preserve repo/test relative fixture overrides when the relative path exists from the current working directory.
- [x] Implement Excel no-header input as Alteryx-style `F1`, `F2`, ... fields.
- [x] Implement `Sort` parser and runtime tool.
- [x] Expand `Select` dtype conversion for observed Alteryx type names such as `Int32`.
- [x] Expand Join default output naming to strip `Left_` and `Right_` prefixes.
- [x] Expand `DbFileOutput` path handling for `%temp%`.
- [x] Copy the externally captured Alteryx CSV oracle into `tests/fixtures/real_workflows/combine_customer_profile_expected.csv`.
- [x] Add parser/tool/registry tests for new Sort support.
- [x] Add Excel input tests for header and no-header sheet reads.
- [x] Add full runtime E2E test: parse -> execute target `23` -> compare CSV oracle.
- [x] Add generated-code E2E test: parse -> generate -> execute target `23` -> compare CSV oracle.
- [x] Add byte-for-byte CSV oracle comparison for runtime and generated-code E2E.
- [x] Add certification precheck for executed node paths.
- [x] Add `docs/basic_advanced_inventory.md`.
- [x] Update certification and testing docs.

### Exit Criteria

- [x] Official workflow parses without hand editing.
- [x] Runtime executes node order `1, 2, 7, 3, 4, 6, 23`.
- [x] Runtime output has 1000 rows and 12 columns matching the Alteryx oracle after CSV parsing.
- [x] Runtime and generated CSV bytes match the Alteryx oracle bytes for this workflow.
- [x] Executed node path passes the certifiable-tool precheck.
- [x] Generated Python writes the same CSV-equivalent output.

### Known Gaps

- [ ] Excel output remains deferred.
- [ ] YXDB input/output remains deferred.
- [ ] `TextBox` documentation nodes are omitted via target execution rather than modeled as no-op tools.
- [ ] This certifies one Basic workflow, not all Basic/Advanced workflows.

## M15 - Lightweight CLI For Repeatable Certification

### Goal

Make repeated workflow certification and edge-case debugging reproducible from the command line.

### Task Checklist

- [x] Add `alteryx2python.cli` module.
- [x] Add `alteryx2python` console script in `pyproject.toml`.
- [x] Add `inspect` command for workflow nodes, edges, tools, dependencies, unsupported nodes, and warnings.
- [x] Add `run` command for target-node execution.
- [x] Add `compare` command with `bytes` and `csv` modes.
- [x] Add `certify` command for run + config-aware certification gate + compare.
- [x] Add `--override-output NODE=PATH` to redirect output nodes to controlled test paths.
- [x] Add `--log PATH` structured JSON logging to every command.
- [x] Ensure unsupported/incomplete behavior emits structured JSON errors with type, message, and traceback.
- [x] Add CLI subprocess tests for inspect, certify, compare mismatch, and unsupported tool behavior.
- [x] Verify CLI certification on the Basic Combine workflow.

### Exit Criteria

- [x] `uv run alteryx2python certify ... --compare bytes` returns `certified` for the Basic Combine workflow.
- [x] CLI byte comparison matches the manual E2E result.
- [x] CLI logs are machine-readable JSON.
- [x] Unsupported behavior is recorded instead of silently passing.

### Known Gaps

- [ ] No batch runner yet.
- [ ] No YAML/JSON suite file format yet.
- [ ] No automatic target/output discovery yet.

## M16 - Node-Level Tool Contracts And Evidence

### Goal

Make each executed Alteryx tool boundary produce machine-checkable contract evidence, so schema and data-shape failures are caught at the first bad intermediate node instead of only at final output comparison.

### Task Checklist

- [x] Define contract evidence structures for assertions, input schemas, and output schemas.
- [x] Attach contract evidence to `NodeResult`.
- [x] Validate declared output anchors for every registered tool.
- [x] Validate parser-provided expected output schema when strict mode is enabled.
- [x] Add inferred contracts for the first high-value tools:
  - `Select`
  - `Formula`
  - `Filter`
  - `Union`
  - `Join`
- [x] Add runtime tests proving successful contract evidence is emitted.
- [x] Add failure tests proving bad schema or anchor output fails fast.
- [x] Include contract evidence in generated-code/runtime certification paths without changing the canonical execution model.
- [x] Update tool docs with contract sections.

### Exit Criteria

- [x] A workflow run exposes per-node contract evidence.
- [x] Schema and row-count assertions are tested for at least `Select`, `Formula`, `Filter`, `Union`, and `Join`.
- [x] Contract failures stop execution before downstream tools consume invalid intermediate data.
- [x] Existing golden-output certification tests still pass.

### Known Gaps

- [ ] Contract assertions are intentionally narrower than full Alteryx semantic parity.
- [ ] Intermediate Alteryx oracle exports are not required for inferred contracts.
- [ ] Full dtype/nullability parity remains a later type-system milestone.

## M17 - Topology-Preserving Compact Workflow JSON

### Goal

Provide an AI-facing workflow representation that saves tokens without deleting logical topology.

### Task Checklist

- [x] Add `build_compact_workflow` for `WorkflowIR`.
- [x] Preserve all node IDs, tool types, anchors, and edges.
- [x] Include graph roots, leaves, and topological order.
- [x] Include per-node incoming and outgoing links.
- [x] Include compact config summaries for core tools.
- [x] Strip raw XML, GUI shell metadata, annotations, and verbose source metadata.
- [x] Add `alteryx2python compact` CLI command.
- [x] Add `inspect --compact` alias.
- [x] Add unit and CLI tests.
- [x] Document compact JSON usage.

### Exit Criteria

- [x] Compact JSON is sufficient to reconstruct the logical workflow graph.
- [x] Compact JSON avoids raw Alteryx UI/config shell payloads.
- [x] Existing runtime and certification tests still pass.

### Known Gaps

- [ ] Compact config summaries are intentionally tool-specific and should expand as more tools are implemented.
- [ ] Compact JSON is for analysis/planning, not a lossless serialized IR.

## Verification Log Template

Use this format when finishing any sub-checklist item:

- Item:
- Files changed:
- Tests run:
- Result:
- Known gaps:
