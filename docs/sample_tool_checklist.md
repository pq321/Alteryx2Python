# Sample Tool Checklist

Source inventory:

- repo samples: `examples/sample_workflows/*.yxmd`, `examples/sample_workflows/*.yxwz`
- official one-tool samples: `D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time`

## Implemented Baseline Runtime Tools

- [x] Action analytic-app metadata edge baseline
- [x] AppendFields
- [x] AutoField
- [x] BlobConvert Base64/Hex/MD5/Text/ReportSnippet conversions
- [x] BlockUntilDone
- [x] Buffer WKT bbox/circle baseline
- [x] BrowseV2 sink
- [x] Condition interface branch payload baseline
- [x] ControlContainer structural no-op
- [x] CrossTab
- [x] CreatePoints WKT spatial placeholder
- [x] DataCleansePro native sample cleanups
- [x] DataCleansing (`Cleanse.yxmc`)
- [x] DateTime
- [x] DateTimeNow with deterministic clock injection
- [x] DbFileInput
- [x] DbFileOutput
- [x] Distance straight-line WKT distance and direction baseline
- [x] Directory local file enumeration
- [x] Download with injected transport or explicit network opt-in
- [x] DynamicRename
- [x] DynamicSelect field-type and schema-formula selection
- [x] Error Message analytic-app validation sink
- [x] FieldInfo
- [x] Filter
- [x] FindNearest WKT nearest-neighbor baseline
- [x] FindReplace
- [x] Formula
- [x] GenerateRows for sample expression patterns
- [x] Generalize WKT duplicate-coordinate compaction baseline
- [x] HtmlBox structural no-op
- [x] Interface controls baseline (`DropDown`, `Label`, `LabelGroup`, `ListBox`, `NumericUpDown`, `QuestionFileBrowse`, `QuestionTab`, `QuestionTextBox`, `RadioButtonGroup`)
- [x] JSONParse
- [x] Join
- [x] JoinMultiple for field joins and record-position joins
- [x] MakeColumns basic row-to-wide reshaping
- [x] MapInput embedded drawn points/polygons
- [x] Message sink
- [x] MultiFieldFormula
- [x] MultiRowFormula for grouped previous-row calculations and moving averages
- [x] PearsonCorrelation pairwise Pearson coefficients and optional covariance
- [x] PolyBuild WKT sequence polygon and convex hull baseline
- [x] Reporting/composer fragment baseline (`PortfolioComposerText`, `PortfolioComposerTable`, `PortfolioComposerImage`, `PortfolioComposerLayout`, `PortfolioComposerRender`, `ReportMap`, `PlotlyCharting`)
- [x] Reporting macro fragment baseline (`ReportHeader`, `ReportFooter`, `ReportLegendSplitter`, `ReportLegendBuilder`)
- [x] Rank
- [x] RecordID, including grouped reset
- [x] RegEx
- [x] RunningTotal
- [x] Sample
- [x] Select
- [x] Sort
- [x] SpatialInfo WKT area, centroid, bounding rectangle, and endpoint baseline
- [x] SpatialMatch WKT bbox matching baseline
- [x] Smooth WKT moving-average coordinate baseline
- [x] SpatialProcess WKT conservative action-selection baseline
- [x] Summarize for non-spatial actions
- [x] Test for record-count and expression assertions
- [x] TextBox structural no-op
- [x] TextInput
- [x] TextToColumns
- [x] Tile for sample tiling methods
- [x] ToolContainer structural no-op
- [x] TradeArea WKT radius polygon baseline
- [x] Transpose
- [x] Union by name and by position
- [x] Unique
- [x] XMLParse for root, selected element, attributes, child values, and outer XML

## Deferred Candidate Tools

These appear in official samples but need broader semantics before they should be marked executable:

- [ ] DynamicInput and DynamicSelect: require dynamic schema/query semantics.
- [ ] Message: control-flow/validation side effects need CLI policy decisions.
- [ ] BlockUntilDone, Detour, DetourEnd, ControlContainer: workflow-control semantics.

## Explicitly Deferred Domains

- Spatial tools beyond CreatePoints, Distance, FindNearest, Generalize, MapInput, PolyBuild, Smooth, SpatialInfo, SpatialMatch, SpatialProcess, and TradeArea
- Full native reporting/composer rendering
- Predictive/machine-learning tools
- Blob/PDF/image/text-mining tools
- Calgary tools
- Interface/action/question tools
- External service connectors without deterministic local transport

## Current Verification

The sample coverage tests parse official sample workflow configs and execute representative local DataFrame fixtures for newly implemented tools. Full-suite verification should be run with:

```powershell
uv run python -m pytest -q
```

Current local generation evidence:

- `uv run alteryx2python generate-samples "D:/Alteryx/Samples/en" --output-dir reports/generated_workflows/all_samples --log reports/generated_workflows/all_samples_manifest.json`
- `uv run alteryx2python generate-samples examples/sample_workflows --output-dir reports/generated_workflows/repo_samples --log reports/generated_workflows/repo_samples_manifest.json`
- Latest run generated 208 official sample scripts and 2 repo sample scripts with zero parse errors.
- Latest official unsupported count is 274 tool instances across 59 tool types; repo samples have 0 unsupported tool instances.
