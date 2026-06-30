# MultiFieldFormula

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Input: `Input`
- Output: `Output`

Implemented semantics:

- selected field normalization from official sample configs
- `[_CurrentField_]` expression binding
- overwrite mode
- copy-output mode with prefix or suffix field names
- expression execution through the canonical expression parser/evaluator

Deferred semantics:

- full Alteryx field type coercion fidelity
- all formula functions beyond the project expression engine
