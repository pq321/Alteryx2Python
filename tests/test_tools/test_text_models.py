import pandas as pd
import pytest
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.text_models import IMPLEMENTATIONS
from alteryx2python.tools.unavailable import ToolUnavailableError

def test_topic_model_produces_fitted_topics():
    out=IMPLEMENTATIONS["TopicModel"]().execute({"Input":pd.DataFrame({"field":["cats cats", "dogs dogs"]})},{"field":"field","topics":2},WorkflowContext())["Output"]
    assert out["Topic"].notna().all()

def test_sentiment_vader_fields():
    out=IMPLEMENTATIONS["Sentiment"]().execute({"Input":pd.DataFrame({"field":["great", "terrible"]})},{"field":"field","algorithm":"VADER"},WorkflowContext())["Output"]
    assert out.loc[0,"positive_sentiment"] > out.loc[1,"positive_sentiment"]
    assert {"negative_sentiment","neutral_sentiment","positive_sentiment","compound_sentiment"} <= set(out)

def test_transformer_never_downloads():
    with pytest.raises(ToolUnavailableError): IMPLEMENTATIONS["TextSummary"]().execute({"Data":pd.DataFrame({"text":["hello"]})},{"text_field":"text"},WorkflowContext())
