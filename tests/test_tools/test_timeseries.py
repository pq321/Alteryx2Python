import numpy as np
import pandas as pd

from alteryx2python.tools.timeseries import (
    IMPLEMENTATIONS, simulation_sampling_tool, tscompare_tool, tsfiller_tool, optimization_tool,
)

def test_sampling_is_seed_deterministic():
    a = simulation_sampling_tool({}, {"samples": 8, "seed": 42}, None)["Output"]
    b = simulation_sampling_tool({}, {"samples": 8, "seed": 42}, None)["Output"]
    assert np.array_equal(a["Sample"], b["Sample"])

def test_filler_and_compare():
    frame = pd.DataFrame({"actual": [1., 2., 3.], "pred": [1., 1., 4.]})
    filled = tsfiller_tool({"Input": frame.assign(actual=[1., np.nan, 3.])}, {"value": "actual"}, None)["Output"]
    assert not filled.actual.isna().any()
    result = tscompare_tool({"Input": frame}, {"actual_field": "actual", "predicted_field": "pred"}, None)["Output"]
    assert result.loc[0, "MAE"] == 2 / 3

def test_expected_exports():
    assert {"ARIMA", "ETS", "TSForecast", "TSFiller", "TSCompare", "TSPlot"} <= set(IMPLEMENTATIONS)

def test_optimization_explicit_lp_and_failures():
    out = optimization_tool({}, {"c": [3, 2], "sense": "maximize", "A_ub": [[1,1],[1,0],[0,1]], "b_ub": [4,2,3]}, None)["Output"]
    assert np.allclose(out.Value, [2, 2]); assert out.Objective.iloc[0] == 10
    bad = optimization_tool({}, {"c": [1], "A_ub": [[-1]], "b_ub": [-1], "bounds": [(0, 0)]}, None)["Output"]
    assert not bool(bad.Success.iloc[0])

def test_factory_model_blob_transport_and_missing_artifact():
    from alteryx2python.tools.timeseries import tsmodel_factory_tool, tsforecast_factory_tool
    frame=pd.DataFrame({"value":np.arange(1.,15.)})
    model=tsmodel_factory_tool({"Input":frame},{"value":"value","p":1},None)["Model"]
    pred=tsforecast_factory_tool({"Model":model},{"horizon":2},None)["Output"]
    assert len(pred)==2 and pred.Forecast.notna().all()
    import pytest
    with pytest.raises(ValueError): tsforecast_factory_tool({}, {"horizon":2}, None)
