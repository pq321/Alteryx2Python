# Differential parity evidence contract

## 1. Scope / trigger
Applies to native Alteryx/Python comparisons, tool coverage and certification claims.

## 2. Signatures
`python -m alteryx2python.parity inventory|coverage|samples|prepare|run|collect|attest|review-bundle|review-check`.
`compare_runs(native: dict, python: dict, *, profile="behavioral") -> dict`; `frame_snapshot(frame) -> dict`.

## 3. Contracts
Snapshots preserve ordered columns/rows, typed JSON cells and independently
derived Alteryx schema (`name`, `type`, `size`, `scale`). Unknown metadata is null.
Node diagnostics are node-local; global arrays contain complete history.
Provenance includes source/instrumented/runtime/engine/output hashes where available.
Official inventory remains independent of catalog and registry; missing IDs stay visible.

## 4. Validation and error matrix
Default behavioral acceptance: both fail regardless of exception class/text, or both succeed with equal per-node data. Known node outcomes must agree; successful upstream checkpoints remain checked after later failure. Numeric values may match across int/float/decimal representations; strings remain distinct, null/empty and row/column order are preserved.
Presentation Step 3 additionally aligns fields by name and accepts checkpoint row permutations with identical records and duplicate counts. Sort outputs and inputs to order-sensitive tools retain ordered comparison. The table views retain original positions and report ordering differences independently of the verdict. File artifact comparison retains its own format-specific rules.
Step 3 reports `coarse_match` separately when its schema-based date, fixed-decimal scale, or nullable text rules explain all remaining checkpoint differences. Preserve raw cells and exact evidence. Exclude protected keys and null-sensitive fields from null/empty normalization. Coarse results do not satisfy the exact delivery gate.
Number new output probes consistently per original tool and output anchor. Native YXDB and its HTML view share the `node<ToolID>-anchor<N>` stem. Input views use `node<ToolID>-input-anchor<N>`. Read existing native files through their capture manifest.
The Step 3 summary attributes a repeated input mismatch to its upstream output only when both captures confirm the input mirrors that output. Detailed evidence retains the input comparison.
Missing node/anchor/outcome evidence => `incomplete`; outcome/data differences => `mismatch`.
Unavailable implementations/dependencies/models/license/executable/timeout => `blocked`, never a matching semantic failure.
Physical schema and raw diagnostics are optional `strict` requirements, not default acceptance gates. Non-match returns nonzero.
Never reuse a run directory for native execution or accept changed workflow hashes.
Python runtime digest mismatch requires explicit recapture against unchanged source.

## 5. Good/base/bad cases
Good: native YXDB records plus independent Python capture match for each anchor.
Base: data/outcomes match but metadata/diagnostics unknown => behavioral match, strict incomplete.
Bad: baseline passthrough or Python-generated golden used as native evidence.

## 6. Required tests
Corrupt rows/schema, remove anchors/nodes, change hashes, preserve null versus empty,
shuffle duplicate rows, exercise failed/blocked executions and official missing IDs.
Regression: native Unique `Duplicates`, Text Input null, overlapping Join columns.

## 7. Wrong versus correct
Wrong: 100% registered tools means identical Alteryx behavior.
Correct: report mapping/parser/runtime inventory separately from versioned,
configuration-specific differential acceptance. Unknown native node diagnostics prevent strict pass. Human review bundles preserve pending confirmations and identify evidence_method=human_review; machine probe comparisons use independently captured native YXDB and outcome attestation. Never auto-fill user confirmation from Python results.

## 8. CLI construction and configuration
Graph specifications preserve unknown source/template XML structurally and resolve native engine bindings from active catalog entries. Do not parse commented EngineSettings with regular expressions. Native construction is separate from configuration execution and proof.
Native Questions/Actions bind before data graph routing, including targeted execution; partial migration slices explicitly use skip_app_configuration. Compiled data workflows remove applied Actions so replacements cannot execute twice. Generated Python preserves all IR fields/source XML and snapshots recursively resolved macro configuration dependencies. File sinks in proof runs are isolated; existing oracle files must never be deleted or overwritten by Python execution. CSV-only comparisons cannot certify null/type/intermediate-node equivalence. Blocked/incomplete proof suites must return nonzero, and tool-case attribution must reference tools present in the tested workflow. Native automation uses EngineCmd; never start/attach Designer or create scheduled tasks to claim guaranteed background execution.

## 9. Disabled branches and call boundaries
Place native output probes beside their source tools in the XML container
hierarchy. Static disabled descendants have an explicit skipped status.
Attest dynamic skips from observed Designer behavior. Compare present zero-row
outputs and treat missing active probes as incomplete. Typed macro replay
inputs must come from the actual caller edges and retain attested file hashes.
Store repeated and nested Python macro executions under caller ID and
invocation number. Preserve the distinction between caller-boundary parity
and parity inside a native macro body.
