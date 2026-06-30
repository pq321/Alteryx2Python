# DynamicReplace

Baseline support applies expression-table-driven field replacement.

- Input anchors: `Input`, `Expressions`
- Output anchors: `Output`, `Counts`
- Current behavior: reads the configured expression table columns, creates or replaces target fields, and evaluates supported Alteryx expressions when `ValueIsExpression` is true.
