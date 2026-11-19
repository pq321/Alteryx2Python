# Sample

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Input: `Input`
- Output: `Output`

Implemented semantics:

- `First`
- `Last`
- `Skip` skips the first N rows
- `Sample` / every Nth row
- `Random` applies an independent 1-in-N chance to each row and preserves input order within a group. Python uses a fixed seed for reproducible Phase One and Phase Two results.
- `NPercent` rounds a fractional half row up
- grouped sampling by configured fields processes groups in sorted order and preserves the order within each group

Deferred semantics:

- exact Alteryx random sequence compatibility
- less common sample modes not present in current tests
