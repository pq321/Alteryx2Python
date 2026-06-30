# Condition Tool

## Coverage

- Parses the Condition interface tool expression from the annotation text.
- Consumes connected `Question` inputs using Alteryx-style ordinal field names such as `[#1]`.
- Emits both `True Condition` and `False Condition` output anchors as one-row payloads.
- Records `expression`, `matched`, branch name, and whether each branch is active.
- Evaluates expressions on a best-effort basis using the existing expression engine.

## Deferred

- Action tool update semantics are not implemented here.
- Unsupported expression functions are preserved as warnings instead of blocking workflow conversion.
- Interactive app prompting and live branch enable/disable behavior remain deferred.
