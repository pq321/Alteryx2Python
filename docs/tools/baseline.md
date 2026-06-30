# Baseline sample tool

Conservative runtime used for Sample Workflow tools that do not yet have full Alteryx semantics.

- Inputs: any DataFrame-bearing anchor.
- Outputs: the node's actual workflow output anchors when available; otherwise `Output`.
- Semantics: passes the first DataFrame input through to each output anchor. Without input, emits a metadata-only row.
- Limitations: does not execute machine-learning training, prediction, OCR, Calgary indexing, assisted modeling, or external services.
- Trace: records `baseline_semantics=passthrough_or_metadata_only`, node anchors, input schemas, and output schemas.
