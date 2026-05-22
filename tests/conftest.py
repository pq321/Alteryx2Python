import pandas as pd
import pytest

from alteryx2python import WorkflowContext


@pytest.fixture
def workflow_context() -> WorkflowContext:
    return WorkflowContext(runtime_config={"mode": "test"})


@pytest.fixture
def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "account": ["A1", "A2", "A3"],
            "amount": [100, 200, 300],
            "fee": [1.5, 2.0, 3.5],
            "flag": [True, False, True],
        }
    )


@pytest.fixture
def null_heavy_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "account": ["A1", None, "A3"],
            "amount": [1, None, 3],
            "flag": [True, None, False],
        }
    )


@pytest.fixture
def empty_frame() -> pd.DataFrame:
    return pd.DataFrame({"account": pd.Series(dtype="string"), "amount": pd.Series(dtype="Int64")})