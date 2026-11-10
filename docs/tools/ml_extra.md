# Local ML extras

`alteryx2python.tools.ml_extra` provides executable local adapters for feature
typing/health/building, numeric transformations, common sklearn modelling,
cross-validation, and simple market-basket summaries. Every adapter requires a
`WorkflowContext` and `source_tool_id`, records a node trace, and returns ordered
pandas frames. Model outputs use the existing local pickle representation.

These implementations are outcome-equivalence evidence for local inputs only;
they are not claims of native Alteryx/R byte compatibility. Native-specific
options and proprietary scoring semantics fail explicitly. `MBAffinity`,
`MBInspect`, and `MBRules` currently expose the same conservative pair-support
summary pending native verification. Forecast factories and association
analysis beyond this summary remain pending.
