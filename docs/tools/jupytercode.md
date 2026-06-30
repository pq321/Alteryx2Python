# JupyterCode

Baseline implementation for Sample Workflow coverage.

- Inputs: first available DataFrame input, usually `Input`.
- Outputs: `Output`.
- Semantics: passes input through, or emits an empty frame when no input exists.
- Safety: never executes embedded Python or installs packages. The script length and venv metadata are recorded in traces.
