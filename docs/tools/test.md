# Test Tool

## Coverage

- Parses one or more configured tests from Developer sample workflows.
- Supports `RecCountValue`, `RecCountMatch`, `ExpAll`, and `ExpFirst`.
- Treats successful tests as a terminal side-effect tool with no output anchors.
- Raises `AssertionError` when a configured check fails.

## Deferred

- Alteryx's UI reporting behavior and `DontReportSubsequent` display policy are recorded but not reproduced beyond parsing.
