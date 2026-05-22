# Architecture

This project follows a structure-first migration path:

1. Parse Alteryx workflow artifacts into a canonical IR.
2. Validate graph, anchors, configs, and support status.
3. Execute or generate Python from IR through registered tool semantics.
4. Compare outputs and schemas against golden evidence.
5. Produce certification-oriented reports.

Key package responsibilities:

- `alteryx2python.ir`: canonical workflow model and validators.
- `alteryx2python.parser`: source parsing into IR.
- `alteryx2python.tools`: tool semantics and metadata registry.
- `alteryx2python.runtime`: execution context, trace, and node execution.
- `alteryx2python.expressions`: controlled expression parsing/evaluation.
- `alteryx2python.comparison`: schema/value comparison and reporting.
- `alteryx2python.generator`: code generation from validated IR.
- `alteryx2python.optimizer`: intentionally disabled for baseline migration.

Real workflow intake starts with the inventory in `docs/workflow_inventory.md`. That document is the authoritative summary of sample-workflow structure, plugin distribution, and external dependency surface for parser and integration planning.

Current parser normalization coverage maps these plugin families to dedicated parsers:

- `AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect` -> `Select`
- `AlteryxBasePluginsGui.DbFileInput.DbFileInput` -> `DbFileInput`
- `AlteryxBasePluginsGui.Formula.Formula` -> `Formula`
- `AlteryxBasePluginsGui.Filter.Filter` -> `Filter`
- `AlteryxBasePluginsGui.JSONParse.JSONParse` -> `JSONParse`
- `AlteryxBasePluginsGui.RecordID.RecordID` -> `RecordID`
- `AlteryxBasePluginsGui.Join.Join` -> `Join`
- `AlteryxBasePluginsGui.Union.Union` -> `Union`
- `AlteryxBasePluginsGui.Transpose.Transpose` -> `Transpose`

Interface, action, and connector plugins remain parsed but deferred until their semantics are explicitly implemented.
