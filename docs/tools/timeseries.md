# Time-series and simulation tools

`alteryx2python.tools.timeseries` provides local pandas adapters for ARIMA, ETS,
TSForecast, TSFiller, TSCompare, TSPlot, SimulationSampling, SimulationScoring,
SimulationSummary, Optimization, CountRegression, GammaRegression, TestOfMeans,
and VarianceInflationFactors. Forecast/regression tools use `statsmodels`; tests
and callers should install that optional dependency (plus scipy and matplotlib).

Adapters preserve the canonical `{"Input": DataFrame} -> {"Output": DataFrame}`
contract. Unsupported distributions and filler methods raise `ValueError`; they
are never silently approximated. SimulationSampling accepts `seed` for repeatable
results. TSPlot additionally returns a `Plot` frame containing the matplotlib
figure for callers that explicitly request a visual artifact.

TSModelFactory emits a local serialized fitted ARIMA model in a Model DataFrame;
TSForecastFactory consumes that anchor without training data. TSCovariateForecast
fits SARIMAX using explicit covariate fields and future_covariates. These are bounded
local profiles; native grouped model factory XML/configuration, native R model bytes,
calendar/seasonal defaults and native report rendering are not certified.
Optimization solves an explicitly configured local linear program through scipy.linprog;
it does not silently invent an objective from an ordinary input table.
