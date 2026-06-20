# Migration Governance

The canonical baseline remains structure-first and tool-boundary preserving.

## Unsupported Classifications

- `safe_to_attempt`: the tool has registered baseline runtime semantics.
- `parsed_only`: the node is structural or metadata-only.
- `owner_review_required`: interface/action behavior or external side effects need workflow-owner review.
- `custom_code_required`: no baseline semantics exist yet.

The shared classifier lives in `alteryx2python.unsupported`.

## Workflow Triage

- Safe to auto-migrate: all execution-path tools classify as `safe_to_attempt`, input/output formats are supported, and a golden fixture exists.
- Partial migration only: at least one branch can execute and produce comparison evidence, but frontier nodes remain skipped.
- Owner review required: interface/action nodes, credentials, connectors, or external side effects affect the path.
- Custom code required: unknown tools, macros, connectors, or unsupported IO formats are required for the target output.

## Adding A New Tool

1. Add or update parser normalization for the observed XML config.
2. Add isolated parser tests.
3. Add a tool implementation under `alteryx2python/tools/`.
4. Register the tool metadata in `TOOL_REGISTRY`.
5. Add success and explicit-deferred/failure tests.
6. Add a tool doc under `docs/tools/`.
7. Add or extend a real workflow integration target.
8. Add comparison evidence if the tool affects a certified output slice.

## Optimizer Gate

Optimizer code remains disabled for canonical baseline migration. It may only become part of an optional layer after the unoptimized baseline has comparison evidence for the same workflow slice.
