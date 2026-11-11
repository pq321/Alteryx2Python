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
