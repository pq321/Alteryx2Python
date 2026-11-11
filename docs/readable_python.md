# Deterministic Two-Phase Python Migration

Phase One preserves the configured workflow in WorkflowIR and emits the existing
baseline Python script. Phase Two reads that preserved representation and lowers
audited templates into ordinary dataframe functions and explicit Python calls.
It does not infer business intent from prose or ask a model to rewrite logic.

The resulting script runs with normal Python libraries, without this repository,
Alteryx, a workflow XML parser, a graph executor, or an expression interpreter. Formula
and Filter expressions become Python expressions. Static macros become ordinary
functions. Node annotations supply useful function names.

## Commands

Run from the repository root in PowerShell:

```powershell
.venv/Scripts/python.exe -m alteryx2python.cli generate examples/readable_benchmark/comprehensive.yxwz --output reports/phase_one.py
.venv/Scripts/python.exe -m alteryx2python.cli readable reports/phase_one.py --output reports/business.py --delivery-profile html-draft-v1
```

The readable command also accepts native workflows and preserved .ir.json files.
It writes the executable .py, a .manifest.json, and an .ir.json sidecar. Execution
does not load the sidecars. Export requires fresh destinations so conversion
cannot overwrite human maintenance work.

The phase-one reader accepts the known generator's AST structure and literal IR
assignments. It never executes the supplied script. Manual behavioral edits are
rejected because silently dropping them would change intent. Such scripts need
an explicit reviewed IR export or a separate migration adapter.

## Editable Output

The compiler emits run_workflow first, followed by dependency-bounded stages and
only the small helpers those stages actually use. It inlines single-use operation
wrappers, resolves file formats, field selections and aggregation modes at compile
time, and prunes unreachable helpers/imports. XML survives only in the IR sidecar.
The manifest records original node IDs, function names, line numbers, template
version, source hashes, bound answers, and field configuration hashes.

NumericUpDown questions replacing literal Formula/Filter operands become named
Python arguments with range and finite-number checks. Integral answers remain
integers. Other action shapes block generation. Macro answers are bound before
static expansion; batch and iterative macros require further lowering templates.

The generated code becomes the owned maintenance source after migration. Do not
regenerate over maintained code. Generate into a fresh directory and use Git
review when intentionally updating a migrated program.

## Compiler Framework

The same pipeline handles every supported workflow configuration:

1. Recognize preserved Phase One IR without executing or interpreting its source.
2. Bind app parameters and expand supported macros using explicit contracts.
3. Schedule data dependencies, branch barriers, containers and observable effects.
4. Select native templates for IO, field conversions, tabular operations,
   relational operations, parsing and reshaping. Remaining audited source templates
   undergo conservative AST specialization. No model infers business logic.
5. Assemble straight-line chains into stages at dependency/fan-out boundaries;
   retain complex lexical scopes where inlining cannot be proved safe. Source
   annotations name stages; unannotated inputs use deterministic operation names.
6. Remove unused code and emit the business source, manifest and preserved IR.

These are compiler rules, not transformations written for individual outputs.
To support a new configuration, extend its template and add differential cases
using different fields, values and topology. Never hand-edit a benchmark output
to make a conversion pass. Helpers implement actual semantics such as decimal
rounding or checked command execution; moving a generic tool runtime into a
second generated module does not satisfy the contract.

Checkpoint collection exists only in ReadableArtifact.verification_source,
assembled from the same operation AST. The shipped source has no checkpoint
parameter, source-node IDs or graph execution machinery. The benchmark executes
both builds and compares their real files as well as the baseline checkpoints.
Both source hashes, compiler modules, package semantic sources, field defaults,
ranking modes and compiler Python/pandas versions are recorded in the manifest.
The semantic source catalogue is deliberately conservative and includes sources
not used by a particular workflow, so changing a shared default is traceable.
User input names that collide with Python/runtime names are allocated safe
identifiers automatically; each parameter records its original and Python name.

## Events And Delivery

Enabled Workflow events execute before processing and after success, failure,
warnings, or clean success according to their serialized timing. Unknown event
types and mail events require dedicated adapters. Macro-local events currently
block static flattening.

Run Command and events require explicit executable allowlists. Windows batch
files run through cmd.exe. Quoted paths and backslashes are preserved. Batch
arguments containing shell metacharacters are rejected rather than interpreted.
Timeouts and nonzero exits propagate. External executable paths are preserved
and must exist on the destination machine.

Configured command/event working directories resolve relative to the input
directory. Verification uses explicit event_working_dir and command_working_dir
overrides to isolate side effects. Generated file sinks use the chosen output
directory. External absolute inputs require explicit portable bindings.

The opt-in html-draft-v1 profile produces basic HTML tables, text, vertical
layouts, HTML files, and deterministic MIME .eml drafts with attachments. It
does not send mail. Grouped/rich reporting and other render formats require
additional templates. Metadata fragments never count as rendered reports.
Legacy callers retain the previous metadata profile unless explicitly opted in.

## Field Sizes

Select and Formula retain and enforce declared type and size:

| Declaration | Current Python Profile |
| --- | --- |
| Byte / Int16 / Int32 / Int64 | Fixed storage widths 1 / 2 / 4 / 8 bytes; invalid widths fail; invalid/overflow values become null with warnings |
| String / V_String | Declared character width, latin-1 replacement, truncation warnings |
| WString / V_WString | Unicode strings with declared width and truncation warnings |
| FixedDecimal, e.g. 8.3 | Decimal arithmetic, width and scale, half-up rounding, invalid/overflow values become null |
| Float / Double | Fixed 4 / 8-byte declarations |

Integer storage width is not a count of decimal digits. Use FixedDecimal or an
explicit range check for a business rule such as at most six digits. Declared
sizes propagate through dataframe schema metadata and Field Info. Boundary
behavior, code pages, supplementary Unicode characters and decimal overflow
require independent native verification before certification.

## Benchmark And Evidence

```powershell
.venv/Scripts/python.exe -m alteryx2python.cli benchmark build --output reports/new-sample
.venv/Scripts/python.exe -m alteryx2python.cli benchmark run --source examples/readable_benchmark/comprehensive.yxwz --output reports/new-acceptance
.venv/Scripts/python.exe -m alteryx2python.cli benchmark inventory --output reports/new-inventory --source examples/readable_benchmark/acceptance/acceptance.json
```

The connected analytic app uses the pinned public UCI Iris snapshot (150 rows,
5 source fields). It includes a standard macro, ordered two-stream blocking
macro, numeric user input, Select/Formula sizes, Generate Rows, multi-field and
multi-row formulas, joins, grouping, reshaping, parsing, containers, commands,
reports, email drafts, and before/after batch events. The blocking macro drains
its first branch before the second; it does not claim CPU parallelism.

The runner executes the actual generated Phase One and Phase Two entrypoints.
It compares every outer node/output anchor with exact dataframe values, dtypes,
row order and declared schema attributes, and hashes all real output files.
Tests also execute a copied script in an isolated directory while rejecting
project imports, and change numeric inputs without recompilation.

The independent inventory retains every pinned official-list row, including
missing configured samples and missing external adapters. It scans local
official examples and emits per-tool IR fixtures and source-linking probes.
Probe inputs are synthetic and never executed. Template compilation differs
from executable coverage; neither proves native equivalence. Incomplete
inventory returns a nonzero exit code.

This is a working migration foundation, not complete support for every Designer
configuration. Proprietary formats, services, credentials, licensed datasets,
models, dynamic macros and unimplemented configurations remain explicit
blockers. The full official-tool requirement remains open until those cases have
real executable fixtures and independent evidence. No placeholder nodes count
as executed coverage.

The EngineCmd probe on November 11, 2026 returned:
The Feature "API or FlowChartMode" is not licensed. Native equivalence remains
unverified. Python-to-Python agreement proves preservation of tested baseline
behavior; it cannot establish that the baseline matches Alteryx.
