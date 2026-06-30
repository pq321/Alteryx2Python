# DynamicInput

Baseline implementation for Sample Workflow coverage.

- Inputs: `Input` optional.
- Outputs: `Output`.
- Semantics: passes the incoming frame through when present; otherwise emits an empty frame.
- Safety: does not read external databases or files. The parsed input configuration and modification mode are recorded in the node trace.
