import pandas as pd
import pytest
from pathlib import Path
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.local_media import IMPLEMENTATIONS

def test_jsonschema_valid_and_invalid():
    out = IMPLEMENTATIONS["JSONSchema"]().execute({"Input": pd.DataFrame({"j": ['{"x": 1}', '{"x": "bad"}']})}, {"field":"j", "schema":{"type":"object","properties":{"x":{"type":"number"}}}}, WorkflowContext())["Output"]
    assert out["JSONSchemaValid"].tolist() == [True, False]

def test_text_preprocessing_and_trace():
    context=WorkflowContext(); out=IMPLEMENTATIONS["TextPreProcessing"]().execute({"Input":pd.DataFrame({"t":[" A  B ", None]})},{"field":"t","mode":"strip"},context)["Output"]
    assert out["t"].tolist() == ["A B", ""]; assert context.traces[0].status == "success"

def test_unknown_text_mode_fails():
    with pytest.raises(ValueError): IMPLEMENTATIONS["TextPreProcessing"]().execute({"Input":pd.DataFrame({"t":["x"]})},{"field":"t","mode":"sentiment"},WorkflowContext())

def test_wordcloud_writes_image(tmp_path: Path):
    path = tmp_path / "cloud.png"
    out = IMPLEMENTATIONS["WordCloud"]().execute({"Input": pd.DataFrame({"text": ["alpha beta alpha"]})}, {"field": "text", "output_path": str(path)}, WorkflowContext())["Output"]
    assert path.exists() and path.stat().st_size > 0
    assert out.loc[0, "WordCount"] == 2

