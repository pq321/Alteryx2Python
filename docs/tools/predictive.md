# Predictive tools

`alteryx2python.tools.predictive` provides local, lazy-imported implementations
for `LinearRegression`, `LogisticRegression`, `DecisionTree`, `ForestModel`,
`NaiveBayes`, `KCentroidsClusterAnalysis`, and `PrincipalComponents`, plus
bounded aliases for `ModelCoefficients`, `Score`, `Fit`, `Predict`,
`Regression`, and `Classification`.

Inputs use the `Input` anchor and config keys `target` (or `target_field`) and
`predictors` (or `features`). Numeric missing values are median-imputed;
categorical predictors are most-frequent-imputed and one-hot encoded. Results
are local pandas frames with a `Prediction` column (or `Cluster` / `PC1...`).

Native ML XML is already normalized by `parser.tool_parsers.ml_tool_parser`:
Classification/Regression/Transformation expose `algorithm_selection` and
`algorithm_configs`; Fit/Predict expose `schema_id`, model identifiers and
designer version. The module exports those existing parsers through `PARSERS`.

Models are internal scikit-learn artifacts and are not native Alteryx/R model
bytes. Unsupported algorithms and missing scikit-learn dependencies fail
explicitly. Randomized estimators default to `random_state=0`; native ordering,
warnings, and model serialization remain outside this adapter's equivalence
claim. Parent integration owns registry/catalog/parser wiring.
