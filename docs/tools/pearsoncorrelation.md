# PearsonCorrelation Tool

## Coverage

- Parses selected `<Fields>/<Field>` entries and the `Covariance` option from one-tool sample workflows.
- Converts selected fields to numeric values and emits one row for each selected field pair.
- Emits `Field1`, `Field2`, and `Correlation`; adds `Covariance` when the option is enabled.
- Expands selected `*Unknown` to remaining numeric input columns.

## Deferred

- Alteryx-specific Results window formatting and matrix-style presentation are not reproduced.
- Inputs with null or non-numeric selected values fail explicitly instead of applying tool-specific imputation.
