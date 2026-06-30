# GenerateRows

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Input: `Input` optional
- Output: `Output`

Implemented semantics:

- creates or updates one iterative field
- supports literal, field-reference, arithmetic, comparison, `If` / `ElseIf` / `Else`, and `DateTimeAdd` expressions used by official samples
- applies iteration per input row when an input frame is present
- enforces a 100000 generated-row safety limit

Deferred semantics:

- complete Alteryx expression language coverage
- exact type coercion for every Alteryx field type
