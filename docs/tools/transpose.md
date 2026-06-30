# Transpose Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- one input anchor named `Input`
- one output anchor named `Output`
- configured key fields are repeated on every output row
- selected data fields become `Name` / `Value` rows
- `ErrorWarn=Warn` skips selected data fields that are absent from the input

Deferred semantics:

- full Alteryx warning/error policy
- output field naming customization
- type coercion and metadata fidelity
