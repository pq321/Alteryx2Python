"""Canonical runtime probes for local macro registrations.

These tests deliberately use the production registry/executor path so missing
integration is visible instead of being hidden by direct function calls.
"""

import pandas as pd
import pytest
import json
from alteryx2python.parity.runner import CaptureContext
from alteryx2python.runtime.executor import run_tool_node
from alteryx2python.tools.registry import TOOL_REGISTRY


def _run(tool_type, frame, config):
    context = CaptureContext()
    metadata = TOOL_REGISTRY.get(tool_type)
    result = run_tool_node(metadata, {"Input": frame}, config, context)
    assert len(context.traces) == 1
    assert context.traces[0].tool_type == tool_type
    assert context.traces[0].source_tool_id == config["source_tool_id"]
    return result


def test_count_records_canonical_output9_contract():
    result = _run(
        "CountRecords",
        pd.DataFrame({"x": [1, 2, 3]}),
        {"node_id": "count-1", "source_tool_id": "CountRecords.yxmc"},
    )
    assert list(result.outputs) == ["Output9"]
    assert result.outputs["Output9"].iloc[0, 0] == 3


def test_select_records_canonical_single_output_and_ranges():
    frame = pd.DataFrame({"x": [1, 2, 3, 4]}, index=[7, 7, 8, 9])
    result = _run(
        "SelectRecords",
        frame,
        {
            "node_id": "select-1",
            "source_tool_id": "SelectRecords.yxmc",
            "ranges": [(1, 2)],
        },
    )
    assert list(result.outputs) == ["Output"]
    assert result.outputs["Output"]["x"].tolist() == [1, 2]


def test_weighted_groups_and_null_values_use_native_config_names():
    frame = pd.DataFrame(
        {"g": ["a", "a", "b", "b"], "v": [2, 6, 8, None], "w": [1, 3, 2, 20]}
    )
    result = _run(
        "WeightedAvg",
        frame,
        {
            "node_id": "w",
            "source_tool_id": "w",
            "Value": "v",
            "Weight": "w",
            "GroupFields": "g",
            "OutputFieldName": "avg",
        },
    )
    assert result.outputs["Output"].to_dict("records") == [
        {"g": "a", "avg": 5.0},
        {"g": "b", "avg": 8.0},
    ]


def test_json_build_grouped_nested_arrays_and_empty():
    frame = pd.DataFrame(
        {
            "g": [1, 1, 2],
            "JSON_Name": ["items.0.name", "items.1.name", "items.0.name"],
            "JSON_ValueString": ["中文", "", "other"],
        }
    )
    config = {"node_id": "j", "source_tool_id": "j", "GroupFields": "g"}
    result = _run("JSONBuild", frame, config).outputs["Output"]
    assert json.loads(result.iloc[0]["JSON"]) == {
        "items": [{"name": "中文"}, {"name": ""}]
    }
    assert json.loads(result.iloc[1]["JSON"]) == {"items": [{"name": "other"}]}
    assert _run("JSONBuild", frame.iloc[:0], config).outputs["Output"].empty


def test_fit_predict_transports_model_without_target_in_new_data():
    model = _run(
        "Fit",
        pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0], "y": [1.0, 3.0, 5.0, 7.0]}),
        {"node_id": "fit", "source_tool_id": "fit", "target": "y", "predictors": ["x"]},
    ).outputs["O"]
    context = CaptureContext()
    result = run_tool_node(
        TOOL_REGISTRY.get("Predict"),
        {"Input": pd.DataFrame({"x": [4.0, 5.0]}), "Model": model},
        {"node_id": "predict", "source_tool_id": "predict"},
        context,
    )
    assert result.outputs["O"]["Prediction"].tolist() == pytest.approx([9.0, 11.0])
    assert (
        len(context.nodes) == 1 and context.nodes["predict"]["tool_type"] == "Predict"
    )


def test_ts_factory_transports_frame_model_without_training_input():
    model = _run(
        "TSModelFactory",
        pd.DataFrame({"y": [1.0, 2.0, 3.0, 2.0, 3.0, 4.0, 3.0, 4.0]}),
        {"node_id": "m", "source_tool_id": "m", "value": "y"},
    ).outputs["Model"]
    context = CaptureContext()
    result = run_tool_node(
        TOOL_REGISTRY.get("TSForecastFactory"),
        {"Model": model},
        {"node_id": "f", "source_tool_id": "f", "horizon": 3},
        context,
    )
    assert len(result.outputs["Output"]) == 3
    assert result.outputs["Output"]["Forecast"].notna().all()
    with pytest.raises(ValueError, match="artifact"):
        run_tool_node(
            TOOL_REGISTRY.get("TSForecastFactory"),
            {},
            {"node_id": "f", "source_tool_id": "f"},
            CaptureContext(),
        )


def test_native_ml_parser_keeps_fields_scalar():
    from alteryx2python.parser.xml_parser import TOOL_PARSERS

    raw = {"field": {"text": "body"}, "algorithm": {"text": "VADER"}}
    config = TOOL_PARSERS["Sentiment"](raw).normalized_config
    assert config["field"] == "body"
    output = _run(
        "Sentiment",
        pd.DataFrame({"body": ["wonderful", "awful"]}),
        {**config, "node_id": "s", "source_tool_id": "s"},
    ).outputs["Output"]
    assert (
        output.iloc[0]["compound_sentiment"] > 0 > output.iloc[1]["compound_sentiment"]
    )
