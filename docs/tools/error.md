# Error Tool

## Coverage

- Parses analytic-app Error Message tool annotations.
- Treats the first non-empty annotation line as the validation expression.
- Uses remaining annotation lines, or the annotation name, as the user-facing message.
- Runs as a terminal validation sink with no output anchors.
- Defaults to non-enforcing mode so converted sample workflows retain app validation metadata without blocking ordinary conversion runs.
- Raises `AssertionError` when `enforce=True`, `enforce_error_messages=True`, or `enforce_interface_errors=True` and the expression evaluates true.

## Deferred

- Full analytic-app question lifecycle and Action updates remain deferred.
- Expressions using unsupported functions still require expression-layer support before enforced execution can evaluate them.
