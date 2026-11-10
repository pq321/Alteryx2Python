# Unavailable execution adapters

All public official identifiers resolve to catalog, parser and runtime dispatch.
Tools needing missing service/data/model resources or unimplemented configuration
adapters raise `ToolUnavailableError`. They never return the input as fake output.

The behavioral comparator classifies these implementation/environment blockers
separately from legitimate workflow failures. An unavailable adapter cannot earn
a matching-failure pass by throwing an error for every input.

`coverage` reports identifier mapping and executable local profiles separately.
`local-*` means candidate local implementations with documented bounds, not
blanket native equivalence. Validate actual configs/results in Designer via
`review-bundle` or instrumented `prepare` / `attest` / `collect` before acceptance.
