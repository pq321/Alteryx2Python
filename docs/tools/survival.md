# Survival and means tools

`SurvivalAnalysis` fits statsmodels `PHReg` using configured duration/event and
predictor fields, emitting a local pickle artifact on `O`. `SurvivalScore`
consumes that artifact on `Model`/`O` and scores new rows without retraining.
`TestofMeans` uses SciPy `ttest_ind` (Welch by default), `ttest_rel`, or
`ttest_1samp` according to `mode`. Outputs use `O` for model/score and `R` for
statistical reports. Pickles are local binary representations, not native
Alteryx model bytes; unsupported modes fail explicitly.
