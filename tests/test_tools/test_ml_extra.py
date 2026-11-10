import pandas as pd
import pytest
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.ml_extra import IMPLEMENTATIONS, PARSERS

def c(name, **kw): return {"source_tool_id": name, **kw}
def test_feature_health_build_transform_and_association():
    f=pd.DataFrame({"x":[1.,2.,3.],"y":[2.,4.,6.]}); ctx=WorkflowContext()
    assert IMPLEMENTATIONS["FeatureTypes"]({"Input":f},c("ft",types={"x":"numeric"}),ctx)["Output"]["x"].dtype.kind=="f"
    assert IMPLEMENTATIONS["DataHealth"]({"Input":f},c("dh"),ctx)["Output"]["NullCount"].tolist()==[0,0]
    assert "z" in IMPLEMENTATIONS["BuildFeatures"]({"Input":f},c("bf",expressions={"z":"x + y"}),ctx)["Output"]
    assert IMPLEMENTATIONS["Transformation"]({"Input":f},c("tr",fields=["x"],method="log1p"),ctx)["Output"]["x"].iloc[0]>0
    tx=f.assign(t=[1,1,2]); assert "Lift" in IMPLEMENTATIONS["MBAffinity"]({"Input":tx},c("mb",transaction_id="t",item_fields=["x","y"]),ctx)["Output"]
def test_predictive_exports_and_cv():
    f=pd.DataFrame({"x":[0.,1.,2.,3.,4.,5.],"y":[1.,3.,5.,7.,9.,11.]})
    for name in ("AutoML","Modeling","BoostedModel","NeuralNetwork","SupportVectorMachine","SplineModel","Stepwise"):
        out=IMPLEMENTATIONS[name]({"Input":f},c(name,target="y",predictors=["x"]),WorkflowContext())
        assert "Output" in out
    out=IMPLEMENTATIONS["CrossValidation"]({"Input":f},c("cv",target="y",predictors=["x"],folds=3),WorkflowContext())
    assert len(out["Output"])==3
def test_fail_closed_and_parser():
    with pytest.raises(ValueError): IMPLEMENTATIONS["FeatureTypes"]({"Input":pd.DataFrame({"x":[1]})},c("x",types={"x":"date"}),WorkflowContext())
    assert PARSERS["FeatureTypes"]({"set_types":[{"attributes":{"field":"x"}}]}).normalized_config["tool_type"]=="FeatureTypes"
