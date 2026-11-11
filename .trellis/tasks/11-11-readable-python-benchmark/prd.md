# Deterministic readable Python and benchmark

Build a reproducible two-phase migration using preserved IR rather than inferred intent.

- Inventory every official tool, including unavailable integrations, independently of execution coverage.
- Provide a connected, executable benchmark with public data, user answers, a local macro, branching, blocking, commands, HTML reports and email drafts. Add per-tool fixtures for the full inventory; unsupported cases must remain visible and blocked.
- Generate ordinary Python functions and explicit calls, without the Alteryx graph runtime, source XML, expression interpreters, or agent decisions in the generated execution path.
- Version templates and emit source/template hashes, node-to-function mappings and a preserved IR sidecar.
- Compare baseline and readable checkpoints and actual artifacts. Track native proof separately; missing licensing/dependencies never count as parity.
- Preserve default compatibility for existing runtime users. Do not send email or run arbitrary imported commands during inventory.
- Verify isolated standalone execution, user-answer changes, macro lowering, failure gates, deterministic output and the complete existing test suite.
