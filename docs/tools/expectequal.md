# ExpectEqual

Baseline support compares two incoming data streams.

- Input anchors: `Actual`, `Expected`
- Output anchors: none
- Current behavior: compares DataFrames after resetting row indexes and records a warning when they differ.
