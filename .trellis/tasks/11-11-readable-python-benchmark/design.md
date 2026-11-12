# Design

## Readability correction: compiler framework, not output repair

The previous source-copying approach made standalone code but retained runtime
configuration machinery. Readability must be a compiler property across inputs.
No benchmark-specific source edits or business-intent inference are permitted.

Cleanup plan:
1. Lower static file/configuration decisions at compile time using native templates.
2. Specialize remaining audited operation ASTs conservatively and prune unused code.
3. Build deterministic straight-line stages from dependency/fan-out boundaries.
   Inline single-use wrappers; preserve scheduling, control guards and effects.
4. Keep source-node mappings in the manifest. Inject checkpoint collection into
   a separate verification build, never into the delivered business source.
5. Test unrelated workflows and changed configurations through the same pipeline,
   in addition to the connected benchmark. Compare all original checkpoints.

Unknown semantics remain compile blockers. Native equivalence remains unverified.

## Web App And Component Audit Follow-up

Use one canonical Phase Two compiler for CLI and Web exports. Remove the
editor's competing generator once its behavioral tests use the canonical path.
Expose runtime implementations from registry metadata while excluding known
unavailable and metadata-only adapters. Preserve complete native workflow XML,
node configuration, engine settings, containers and connection attributes.

Add explicit dynamic versus specialized exports. Specialized mode binds the
chosen answers and variables before native lowering, including static structural
Actions; dynamic mode retains supported Python parameters. Record the decision
and fixed values in the manifest. No agent inference or output-specific repair.

Expose macros/dependency uploads, lifecycle events, Questions/Actions, constants,
runtime permissions and generated artifacts through the TypeScript editor. Keep
XML as the complete configuration escape hatch alongside convenient forms. Add
persistent Chinese/English controls without translating user data or code.

Validate the real HTTP and browser paths, including import/save/reload, connected
custom macro definitions, configuration edit conflicts, stale artifact paths and
language switches. Independent review findings require regression evidence.

## November 12 coverage expansion

Audit the official inventory separately from runtime implementations and native
source compilation. Extend the existing framework, never individual outputs.
Bundle app questions and Actions with their target operations; preserve named
Python parameters across repeated runs. Expand literal expression parameters and
explicit file bindings before extending other configuration contracts.

Replace the Python Tool passthrough with deterministic AST lowering of the
configured script and explicit read/write boundaries. Keep user code intact,
support numbered inputs/outputs, and reject unresolved vendor API calls.
Validate official/static/nested macros, lifecycle events and variable resolution
through the same canonical and readable paths. Track external prerequisites and
missing semantics independently; registration never counts as execution proof.

Phase one remains the canonical XML parser, WorkflowIR and PythonGenerator. Phase two uses native configuration-specific templates, conservative AST specialization for other audited operations, and dependency-based stage assembly. Expressions lower from the existing AST into Python syntax; no expression strings are evaluated at runtime. Unknown operations, dynamic control, metadata placeholders and unresolved macros block generation.

A source linker specializes required helpers and ordinary library imports. The assembler removes operation wrappers and unreachable definitions, presents orchestration first, and separates checkpoint instrumentation into a verification build. Every emitted operation records its implementation digest. The generated project needs pandas and ordinary libraries, not this repository. Static macros lower recursively after binding questions/actions.

The benchmark has a connected integration workflow and an independently inventoried tool suite. Tool presence, successful parsing, compilability, executed differential tests and native certification are separate counters. External services, proprietary macro packages, predictive assets and engine licensing remain explicit blockers.

Reports and email use an explicit html-draft-v1 migration profile, preserving the legacy metadata profile by default. Command execution requires an explicit allowlist in verification. All generated sinks are relocated to fresh output directories.

## November 12 Implementation And Evidence

Question/Action/target groups now lower supported text, date, dropdown, file,
numeric and Boolean controls into named Python parameters. Boolean actions can
disable Tool/Control Containers at runtime, including descendant guards.
Ambiguous raw expression escaping is rejected. Conditional/formula/raw XML
Actions remain blocked rather than interpreted.

Saved Python Tool ASTs retain ordinary user code while lowering numbered IO,
metadata and constant API boundaries. Both canonical execution and delivered
source execute the installed official Python sample. User names and nested
signatures are protected from instrumentation removal. Package installation and
unmapped vendor APIs remain explicit blockers.

User/Global declarations use nested variable scopes; parent overrides do not leak
into macros. Embedded nested macro outputs retain their boundary ownership after
source removal. Static helper configurations are expanded only when their uses
are read-only; mutation and aliases block compilation. Audited input boundaries
become explicit dataframe arguments, with source hashes retained.

WaitASecond/WaitSeconds have an explicit delay contract. The new html-smtp-v1
profile uses standard-library SMTP and execution-time environment settings.
Transport tests are mocked; no real mail is sent. Draft/report defaults remain.

Final validation: 1,193 tests pass, 85.86% coverage, seven warnings. The connected
benchmark matches 38 outer checkpoints and eight files; delivered source executes
independently. Inventory scans 293 sources and retains 323 official rows: 89
configured compile successes, 96 external prerequisites, 85 missing fixtures and
53 blocked isolated configurations (including interface nodes needing grouped
fixtures). Native Alteryx equivalence is unverified. Detailed evidence and open
contracts are recorded in docs/component_mapping_status.md. Task remains in
progress because universal component/configuration coverage is not complete.
