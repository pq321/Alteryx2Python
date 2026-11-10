# CLI continuation acceptance

User authorized a complete CLI audit and fixes, general graph generation/editing,
macros/questions and broader configuration-specific proof. Reused the active task;
all initial dirty work was preserved and no commits/archives were created.

Implemented catalog-backed WorkflowSpec/NodeSpec/EdgeSpec with templates, explicit
engine bindings, connection checks, source XML preservation and resource relocation.
CLI now includes general generate-workflow --spec, workflow-export/edit, node-template,
validate-workflow, tools, questions, configure-workflow, run-python and proof-suite.
Generated Python preserves all IR/source metadata and embeds local macro XML recursively;
direct execution and execution after workflow/nested macro deletion are tested.

Native RuntimeProperties Question defaults/answers, typed validation, condition/action
application and compiled data graphs are separate from data execution. Targeted runs
also apply configuration by default; intentional partial slices explicitly opt out.
Standard Value parameters, single-control batch iteration, declared-schema empty batches,
and bounded iterative feedback are tested on actual transformed values. Complex field maps,
dynamic selection UI, specialized Actions and all native iteration modes remain uncertified.

Native runner now preserves existing oracles, binds diagnostics to its process, recognizes
warning return codes, distinguishes blocked/failed, and does not launch Designer or create
scheduled tasks. Final-CSV scope is explicit; node proof reuses YXDB snapshots with sink
isolation and macro dependency hashes. Blocked-only suites return nonzero. Proof manifests
cannot claim absent tools. Formula active engine metadata and RegEx/CrossTab entry names
were fixed; quoted attributes and UTF-8 CSV options were covered.

Final verification:649 tests pass,84.12% coverage,4 fixture/dependency warnings.
13 CLI calls and direct converted-script execution passed acceptance;6 Python graph cases
have asserted data values.3 native macro attempts are explicitly blocked by API/FlowChartMode
licensing. Existing real-native fixture replay passes but is not a new native run.
Official inventory refreshed:323 rows,321 unique IDs,no changes;226 executable profiles,97
resource/adapter gaps. Evidence:docs/tools/evidence/2026-11-10-cli and reports/cli-acceptance/2026-11-10.

Python review findings addressed: targeted defaults, declared empty batch schemas; a later
embedded-macro concern was checked against current code and source-deletion tests and was
stale. Native Question/Action equivalence must still be independently checked in Designer;
comparing a Python-compiled data graph does not prove the native configuration compiler.

Task remains in_progress because universal all-tool semantic losslessness is not achieved.
