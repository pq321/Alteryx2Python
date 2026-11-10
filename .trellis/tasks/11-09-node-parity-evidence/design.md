# Design

## CLI continuation 2026-11-10
Catalog-backed JSON NodeSpec/EdgeSpec owns construction and validation; native templates and source XML preserve unknown properties and Questions. WorkflowIR and generated Python carry source XML, anchors, metadata and dependencies. App binding runs as a separate configuration stage before data execution using RuntimeProperties questions, conditions and actions. Macro callers bind Value names; standard, single-control batch and bounded iterative graph profiles reuse canonical execution. Construction, execution profiles, final-CSV equality and per-node native evidence remain separate claims. Headless EngineCmd is the supported background channel; the undocumented GUI/scheduled-task channel must not disturb the restored user session.

## Revised default contract
Default profile is behavioral outcome/result equivalence, as explicitly clarified by the user. Compare success versus failure, and values for successful outputs. Exception names/text and physical schema metadata are supplementary diagnostics; strict profiles may opt into them. Manual native outcomes can be attested node-by-node with source/probe hashes, preserving provenance and invalidating stale captures.

Implement independent tool families in separate modules exporting IMPLEMENTATIONS, ANCHORS and optional PARSERS. The parent integrates registry/catalog changes to avoid concurrent mutations. Every official identifier resolves to a stable canonical mapping; unimplemented proprietary/service adapters explicitly fail with prerequisites instead of passthrough.

Add an isolated parity package without rewriting dirty parser/runtime work. A capturing WorkflowContext delegates trace recording and snapshots full records. Instrument a workflow copy with one YXDB output per node/output anchor. Read native records and field metadata using the optional open-source yxdb reader. Preserve the original graph and file.

Serialize typed values and ordered schemas. Unknown Python metadata stays unknown and yields incomplete evidence. Strict pass requires complete evidence and matching diagnostics. Equal errors alone are not successful equivalence. Hash source/instrumented workflows; reject stale output directories. Native runs have timeouts and raw logs. Allow manual Designer execution when Engine API access is unavailable.

Official inventory is independent of the local registry and includes missing identifiers. Do not create passthroughs to inflate coverage. Separate mapping/parser/runtime maturity from differential evidence. Scope: local 2025.1 and current official docs retrieved on 2026-11-09.
