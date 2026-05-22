from typing import cast

import pandas as pd
import pytest

from alteryx2python.comparison.schema_diff import ensure_fields_exist
from alteryx2python.tools.select import select_tool


def test_select_requires_input_anchor(workflow_context):
    with pytest.raises(KeyError, match="Input anchor"):
        select_tool(inputs={}, config={"select_fields": [{"source": "account"}]}, context=workflow_context)


def test_select_requires_dataframe_input(workflow_context):
    with pytest.raises(TypeError, match="DataFrame"):
        select_tool(
            inputs=cast(dict[str, pd.DataFrame], {"Input": [1, 2, 3]}),
            config={"select_fields": [{"source": "account"}]},
            context=workflow_context,
        )


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({}, "non-empty select_fields list"),
        ({"select_fields": []}, "non-empty select_fields list"),
        ({"select_fields": ["account"]}, "dictionary"),
        ({"select_fields": [{}]}, "source field"),
    ],
)
def test_select_validates_config_shape(config, message, sample_frame, workflow_context):
    with pytest.raises((ValueError, TypeError), match=message):
        select_tool(inputs={"Input": sample_frame}, config=config, context=workflow_context)


def test_select_rejects_missing_input_field(sample_frame, workflow_context):
    with pytest.raises(KeyError, match="Missing input fields: missing_col"):
        select_tool(
            inputs={"Input": sample_frame},
            config={"select_fields": [{"source": "missing_col"}]},
            context=workflow_context,
        )


def test_select_rejects_duplicate_output_names(sample_frame, workflow_context):
    with pytest.raises(ValueError, match="Duplicate output field names"):
        select_tool(
            inputs={"Input": sample_frame},
            config={
                "select_fields": [
                    {"source": "account", "rename": "dup"},
                    {"source": "amount", "rename": "dup"},
                ]
            },
            context=workflow_context,
        )


def test_select_rejects_unsupported_dtype(sample_frame, workflow_context):
    with pytest.raises(ValueError, match="Unsupported Select dtype conversion"):
        select_tool(
            inputs={"Input": sample_frame},
            config={"select_fields": [{"source": "amount", "dtype": "decimal"}]},
            context=workflow_context,
        )


def test_ensure_fields_exist_accepts_present_columns(sample_frame):
    ensure_fields_exist(sample_frame, ["account", "amount"])


def test_ensure_fields_exist_raises_for_missing_columns(sample_frame):
    with pytest.raises(KeyError, match="Missing input fields: x, y"):
        ensure_fields_exist(sample_frame, ["x", "y"])


def test_select_preserves_series_values_when_dtype_unspecified(sample_frame, workflow_context):
    result = select_tool(
        inputs={"Input": sample_frame},
        config={"select_fields": [{"source": "flag"}]},
        context=workflow_context,
    )

    assert result["Output"]["flag"].tolist() == [True, False, True]
    assert str(result["Output"]["flag"].dtype) == "bool"