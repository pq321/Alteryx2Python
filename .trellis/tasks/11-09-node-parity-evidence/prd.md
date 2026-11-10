# Node parity evidence

## Goal
Provide reproducible local learning workflows and honest, per-node evidence for Alteryx/Python equivalence across inputs, outputs, schema, ordering, warnings and errors. Track all officially listed tools, including gaps.

## Facts
The working tree started with 48 changed/untracked paths. Local engine: 2025.1.2.165. Catalog registration includes baseline stubs and is not semantic proof. Current traces contain counts/schema summaries, not complete records.

## Acceptance
- 2026-11-10 continuation: audit and repair preset/native/equivalence CLI; add general catalog-backed graph generation/editing, exact node templates, yxmc and native question/action configuration; preserve all existing dirty changes and the restored Designer environment. Default remains outcome/result equivalence, never blanket universal proof.
- User clarification: default equivalence is outcome equivalence. Both fail => matching outcome regardless of exception class/message; both succeed => compare observable node results. Raw diagnostics and physical metadata remain optional detailed profiles, not default blockers.
- Implement mappings and executable local behavior, not only audits. Cover the complete official identifier inventory; explicit unavailable adapters must fail rather than silently return input. Distinguish mapping completion from implemented behavior and validated cases.
- Deliver a manual Designer review bundle: original workflow, runnable corresponding Python, full per-node outputs, checkpoint checklist, user-recorded native outcomes and repeatable comparison. Engine API is not required for this route.
- Official tools snapshot records source URL, retrieval time and content hash; coverage includes unresolved mappings.
- Generate local branching, join, empty-output, null/Unicode and failing workflows.
- Compare anchor identity, column/row order, duplicates and null versus empty by default. Preserve physical field metadata/raw errors for the optional strict profile. Missing required evidence cannot pass.
- Native outputs come from an actual engine run or manually run instrumented workflow, never Python-generated goldens.
- Python uses the canonical runtime. Reports preserve logs and distinguish blocked, mismatch and incomplete evidence.
- Tests corrupt data and cover missing anchors, failed runs, stale artifacts and catalog gaps.

## Limits
Local learning only. No production workflows or network connectors are executed. Universal equivalence remains a per-configuration acceptance target. Add-ons, external services, UI interaction and licenses remain explicit prerequisites.
