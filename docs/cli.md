# CLI

The CLI is a lightweight certification and debugging wrapper around the existing parser, runtime, comparison, and certification gate.

It is intentionally JSON-first:

- every command prints a structured JSON report to stdout
- `--log PATH` writes the same JSON report to disk
- successful certification exits `0`
- mismatches exit non-zero
- runtime or unsupported-behavior errors still produce structured JSON with error type, message, and traceback
- failed `run` and `certify` commands include support diagnostics with failed-node context, input traces, likely cause, and suggested fix

## Commands

Inspect a workflow:

```powershell
uv run alteryx2python inspect "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd" --log E:/tmp/inspect.json
```

Emit a topology-preserving compact workflow JSON:

```powershell
uv run alteryx2python compact "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd" --log E:/tmp/compact.json
```

The same compact view is available through:

```powershell
uv run alteryx2python inspect "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd" --compact
```

Emit a change-request support surface map:

```powershell
uv run alteryx2python support-map "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd" --log E:/tmp/support-map.json
```

`support-map` statically identifies nodes that support engineers commonly edit during automation maintenance: input files, output/attachment files, report body fragments, report tables, report layout/render nodes, and subject/recipient candidates when present. The same map is also included in `compact` output so graph analysis and change-request analysis stay together.

Generate a Python script for one workflow:

```powershell
uv run alteryx2python generate "D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/02 Preparation/Formula.yxmd" --output "E:/tmp/generated/Formula.py" --log "E:/tmp/generated/Formula.json"
```

Generate Python scripts for a sample workflow directory:

```powershell
uv run alteryx2python generate-samples "D:/Alteryx/Samples/en" --output-dir "reports/generated_workflows/all_samples" --log "reports/generated_workflows/all_samples_manifest.json"
```

`generate-samples` preserves the source directory layout under `--output-dir`, writes one `.py` file per `.yxmd`/`.yxwz`, and reports unsupported nodes per workflow so the remaining tool backlog stays visible.

Run a target node:

```powershell
uv run alteryx2python run "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd" --target-node 23 --override-output 23=E:/tmp/Excel.CustomerProfileOutput.csv --log E:/tmp/run.json
```

Compare files:

```powershell
uv run alteryx2python compare --actual E:/tmp/Excel.CustomerProfileOutput.csv --expected tests/fixtures/real_workflows/combine_customer_profile_expected.csv --mode bytes --log E:/tmp/compare.json
```

Certify a workflow target:

```powershell
uv run alteryx2python certify "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd" --target-node 23 --override-output 23=E:/tmp/Excel.CustomerProfileOutput.csv --expect tests/fixtures/real_workflows/combine_customer_profile_expected.csv --compare bytes --log E:/tmp/certify.json
```

Expected certified status:

```json
{
  "status": "certified",
  "execution_order": ["1", "2", "7", "3", "4", "6", "23"],
  "certification_issues": [],
  "contract_evidence": {
    "7": {
      "passed": true
    }
  },
  "compare": {
    "mode": "bytes",
    "matches": true,
    "first_difference": null
  }
}
```

## Contract Evidence In Reports

Successful `run` and `certify` reports include:

- `contract_evidence`: compact per-node assertion evidence keyed by node ID
- `runtime_result`: full runtime result export, including per-node outputs and nested `contract_evidence`
- `trace`: execution trace and context warnings/errors

Use `contract_evidence` to find the first node whose schema, output anchor, or row-count assertion failed. Use `runtime_result` when a downstream tool needs the full node-level output summary for debugging.

## Support Diagnostics In Error Reports

The pipeline is also a support runtime for bug fixes and change requests. Failed `run` and `certify` commands include `diagnostics` so support engineers do not have to inspect a raw Python traceback or reopen Alteryx Designer just to find the failing tool.

Diagnostics include:

- stable error code such as `missing_input_fields`, `missing_input_file`, `missing_input_anchor`, `missing_upstream_output_anchor`, `unsupported_tool`, or `node_execution_failed`
- failed workflow and node identity
- tool type, supported status, anchors, and compact config summary
- incoming/outgoing graph context
- shallow macro provenance for `.yxmc` / `.yxwz` backed nodes
- input row counts, columns, dtypes, and null counts
- missing fields and fuzzy field suggestions for schema drift
- likely cause and suggested fix

See [support_diagnostics.md](support_diagnostics.md) for the support contract and examples.

## Compact Workflow JSON

The `compact` command is the AI-facing view of an Alteryx workflow. It preserves the logical topology while stripping raw XML and GUI shell data.

It keeps:

- workflow identity, node count, and edge count
- every node ID and tool type
- every input and output anchor
- every edge as `from_node:from_anchor -> to_node:to_anchor`
- graph roots, leaves, and topological order
- per-node incoming and outgoing links
- compact tool config summaries
- compact schema field names/types when available
- unsupported status, warnings, and external dependencies
- `support_map` for change-request surfaces such as input/output files, report body/table/layout/render nodes, attachments, and subject/recipient candidates

It removes:

- raw XML payloads
- GUI coordinates and canvas layout
- annotation/UI shell metadata
- verbose `MetaInfo` source paths
- large embedded row payloads where a row count is enough for workflow reasoning

Use compact JSON when asking an AI agent to analyze workflow structure, migration order, unsupported tools, or node-level conversion plans. Use the full parser/runtime reports when debugging exact XML parsing or execution behavior.

## Output Overrides

Use `--override-output NODE_ID=PATH` to redirect an Alteryx output node to a controlled test path. This is the recommended pattern for repeatable tests because many official samples write to `%temp%`.

## Compare Modes

- `bytes`: byte-for-byte file comparison. Use this for strict replication.
- `csv`: parses both files with pandas and compares shape, schema, and values. Use this when byte output is expected to differ but tabular payload should match.

## Unsupported Behavior Logs

Unsupported tools or incomplete behavior are reported as structured errors. Example:

```powershell
uv run alteryx2python run "D:/Alteryx/Samples/en/04 Basic/01 Normalize_a_string_field.yxmd" --target-node 97 --log E:/tmp/unsupported.json
```

The JSON report includes:

- `status: "error"`
- `error.type`, such as `NotImplementedError`
- `error.message`, such as `Unsupported workflow tool: RegEx (node 97)`
- `error.traceback`

These logs are intended to become the backlog for the next tool implementation pass.
