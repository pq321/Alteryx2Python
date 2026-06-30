# Pipeline Support Diagnostics

The pipeline is not only an Alteryx-to-Python converter. It is also a support runtime for automation change requests and production bug triage.

## Goal

Alteryx Designer errors often stop at "this tool failed". Support work needs a richer answer:

- which workflow failed
- which node failed
- what the node does structurally
- which upstream data reached it
- which columns, anchors, files, or tool behaviors changed
- what to check next

The pipeline error handler therefore emits structured diagnostics alongside the normal runtime error.

## Diagnostic Report Shape

Failed `run` and `certify` reports include:

- `diagnostics`: support-focused node failure reports
- `trace.diagnostics`: the same diagnostics inside the runtime context export
- `trace.traces`: successful node traces plus the failed node trace when the failing node was reached

Each diagnostic contains:

- `code`: stable machine-readable category such as `missing_input_fields`, `missing_input_file`, `missing_input_anchor`, `missing_upstream_output_anchor`, `unsupported_tool`, or `node_execution_failed`
- `summary`: one-line support summary
- `likely_cause`: probable source of drift or failure
- `suggested_fix`: next action for a support engineer
- `workflow`: workflow identity and source file
- `node`: node id, tool type, supported status, anchors, and compact config summary
- `node.macro_context`: shallow macro provenance when a node is backed by `.yxmc` or `.yxwz`
- `graph_context`: incoming and outgoing workflow edges with neighboring tool types
- `inputs`: per-anchor row counts, columns, dtypes, and null counts
- `expected_fields`, `missing_fields`, and `field_suggestions` when the failure looks like schema drift

## Covered Support Scenarios

Initial diagnostics cover these common support cases:

- wrong or missing input file
- missing input anchor
- missing upstream output anchor
- unsupported tool or unsupported tool behavior
- upstream schema drift, especially missing or renamed columns
- generic node execution failure with node, graph, config, and input traces

## Example: Column Rename Drift

If a `Select` node expects `customer_id` but upstream data now provides `client_id`, the CLI returns a non-zero exit code and a report shaped like:

```json
{
  "status": "error",
  "diagnostics": [
    {
      "code": "missing_input_fields",
      "node": {
        "id": "17",
        "tool_type": "Select"
      },
      "missing_fields": ["customer_id"],
      "field_suggestions": {
        "customer_id": ["client_id"]
      },
      "likely_cause": "Upstream data no longer provides customer_id...",
      "suggested_fix": "Check node 17's upstream input schema..."
    }
  ]
}
```

This is the support-facing contract: errors must be actionable without opening Alteryx Designer just to rediscover the failing node's role.

## Change Request Use

For report and email workflows, diagnostics should be read together with compact workflow JSON:

1. Use `support-map` or the `support_map` section inside `compact` to identify the nodes that shape subject text, HTML body, table data, output files, and attachments.
2. Use `run` or `certify` diagnostics when a requested change breaks a downstream node.
3. Use `graph_context` to navigate from the failed node back to the upstream data or formatting node that needs the edit.

The first support map extractor covers input/output files, report text/body fragments, report tables, layout/render nodes, attachments, subject/recipient candidates when these are visible in parsed node configs, and shallow macro provenance for macro-backed nodes. Future work should deepen macro call-chain expansion and provider-specific email send tools.
