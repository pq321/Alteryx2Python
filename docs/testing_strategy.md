# Testing Strategy

Testing is split by responsibility rather than by implementation convenience.

Current layout:

- `tests/test_tools`: tool-level semantic tests
- `tests/test_runtime`: runtime and executor tests
- `tests/test_ir`: IR-level tests
- `tests/test_parser`: parser contract tests
- `tests/test_expressions`: expression-layer tests
- `tests/test_generator`: generator tests
- `tests/test_integration`: workflow-level tests
- `tests/fixtures`: reusable input, golden output, YXMD, and expected IR assets

Select remains the only implemented tool slice today, but the test layout is now ready for additional tools and workflow-level evidence.
