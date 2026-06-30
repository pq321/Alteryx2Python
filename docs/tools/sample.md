# Sample

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Input: `Input`
- Output: `Output`

Implemented semantics:

- `First`
- `Last`
- `Sample` / every Nth row
- deterministic `Random`
- `NPercent`
- grouped sampling by configured fields

Deferred semantics:

- exact Alteryx random seed compatibility
- less common sample modes not present in current tests
