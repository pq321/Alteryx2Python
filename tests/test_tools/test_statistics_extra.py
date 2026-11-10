import pandas as pd
import pytest
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.statistics_extra import IMPLEMENTATIONS, PARSERS

def ctx(): return WorkflowContext()
@pytest.mark.parametrize("name", ["DistributionAnalysis","Histogram","Scatterplot","HeatPlot","ViolinPlot","PlotofMeans","ImportanceWeights","AssociationAnalysis","FindNearestNeighbors","AppendCluster","KCentroidsDiagnostics","MultidimensionalScaling","NetworkAnalysis","ModelComparison","LiftChart","ABAnalysis","ABControls","ABTreatments","ABTrend"])
def test_local_profile_produces_nontrivial_output(name):
    f=pd.DataFrame({"x":[1.,2.,4.,8.],"y":[2.,1.,3.,5.],"g":["a","a","b","b"],"source":["a","a","b","b"],"target":["b","b","a","a"],"outcome":[0,1,1,1],"time":[1,2,1,2]})
    c={"source_tool_id":"test-"+name,"fields":["x","y"],"group":"g","seed":3,"clusters":2,"k":2,"target":"outcome","score":"x","time":"time"}
    result=IMPLEMENTATIONS[name]({"Input":f},c,ctx())["Output"]
    assert isinstance(result,pd.DataFrame) and len(result)>0
@pytest.mark.parametrize("name", ["DistributionAnalysis","Scatterplot","AppendCluster"])
def test_missing_field_and_null_are_rejected(name):
    with pytest.raises(KeyError): IMPLEMENTATIONS[name]({"Input":pd.DataFrame({"x":[1]})},{"source_tool_id":"x","fields":["missing"]},ctx())
    with pytest.raises(ValueError): IMPLEMENTATIONS[name]({"Input":pd.DataFrame({"x":[1,None],"y":[2,3]})},{"source_tool_id":"x","fields":["x","y"]},ctx())
def test_parser_preserves_scalar_settings():
    assert PARSERS["Histogram"]({"Field":{"text":"x"},"Seed":{"value":"7"}}).normalized_config["Field"]=="x"
