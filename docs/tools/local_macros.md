# Local macro implementations

`alteryx2python.tools.local_macros` contains executable offline implementations
for baseline local macros. Each callable accepts `(inputs, config, context)` and
returns anchor-name to `pandas.DataFrame`; successful calls record a node through
`context.record_node`.

Implemented identifiers are CountRecords, WeightedAvg, SelectRecords,
Base64Encoder, JSONBuild, SpearmanCorrCoeff, FrequencyTable (the canonical name
for Frequency), ContingencyTable, Imputation, RandomRecords, CreateSamples,
MultiFieldBinning, OversampleField, and FieldSummaryReport. Unsupported modes
raise explicitly. These are behavioral local equivalents, not vendor code or a
claim of universal configuration equivalence.

## Installed sample evidence

The 2025.1 samples were inspected under `D:\Alteryx\Samples\en`. `CreateSamples.yxmd`
uses `Value name="estimation pct"`, `validation pct`, and `rand seed`; it describes
Estimation, Validation, and optional Holdout samples. `OversampleField.yxmd` uses
`Selected_Field`, `Oversample_Value`, and `Desired_Pct`, with a single output stream.
`Imputation.yxmd` uses the `listbox Select Incoming Fields` and radio values
`Mean`, `Median`, `Mode`, and user-specified replacement flags. Base64's sample
uses `Input.Macro Input` (`Text=Field1`). These names are accepted by `PARSERS`.

References: [Alteryx Create Samples tool](https://help.alteryx.com/current/en/designer/tools/predictive/create-samples-tool.html),
[Alteryx Oversample Field tool](https://help.alteryx.com/current/en/designer/tools/predictive/oversample-field-tool.html),
[Alteryx Imputation tool](https://help.alteryx.com/current/en/designer/tools/data-investigation/imputation-tool.html).

Limitations: macro XML can vary by Designer release; unknown modes/configuration
keys are not inferred. Native engine/API execution remains license-dependent.
