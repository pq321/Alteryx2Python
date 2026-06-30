# DynamicRename Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- one input anchor named `Targets`
- one output anchor named `Output`
- Formula rename mode
- `_CurrentField_` expression variable for field-by-field rename formulas
- duplicate output names fail explicitly

Deferred semantics:

- non-formula rename modes
- field metadata updates beyond column names
- dynamic unknown-field behavior outside observed workflow usage
