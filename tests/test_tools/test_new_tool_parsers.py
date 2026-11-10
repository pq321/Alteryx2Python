from __future__ import annotations

from alteryx2python.parser.tool_parsers.calgary_parser import parse_calgaryinput_config
from alteryx2python.parser.tool_parsers.canvas_parser import (
    parse_htmlbox_config,
    parse_message_config,
    parse_textbox_config,
    parse_toolcontainer_config,
)
from alteryx2python.parser.tool_parsers.catalog_parser import parse_catalog_config
from alteryx2python.parser.tool_parsers.ml_tool_parser import make_ml_parser


def _field(value):
    return {"text": value}


def test_parse_textbox_config():
    raw = {
        "Text": _field("Bring data into a workflow"),
        "Font": {"attributes": {"name": "Segoe UI", "size": "15.75"}},
        "TextColor": {"attributes": {"r": "214"}},
        "FillColor": {"attributes": {"name": "White"}},
        "Shape": {"attributes": {"shape": "3"}},
        "Justification": {"attributes": {"Justification": "0"}},
    }
    result = parse_textbox_config(raw)
    assert result.normalized_config["text"] == "Bring data into a workflow"
    assert result.normalized_config["font"]["name"] == "Segoe UI"
    assert result.normalized_config["shape"] == "3"


def test_parse_htmlbox_config():
    raw = {"URL": _field("..\\Tutorial12.htm"), "HideAddressBar": {"attributes": {"value": "True"}}}
    result = parse_htmlbox_config(raw)
    assert result.normalized_config["hide_address_bar"] is True
    assert result.normalized_config["url"].endswith("Tutorial12.htm")


def test_parse_toolcontainer_config():
    raw = {
        "Caption": _field("Sample date data"),
        "Style": {"attributes": {"TextColor": "#364b4a"}},
        "Disabled": {"attributes": {"value": "False"}},
        "Folded": {"attributes": {"value": "True"}},
    }
    result = parse_toolcontainer_config(raw)
    assert result.normalized_config["caption"] == "Sample date data"
    assert result.normalized_config["disabled"] is False
    assert result.normalized_config["folded"] is True


def test_parse_message_config():
    raw = {
        "When": _field("First"),
        "Filter": {},
        "Type": _field("Message"),
        "Priority": _field("Normal"),
        "Transient": _field("False"),
        "MessageExpression": _field('"hello"'),
    }
    result = parse_message_config(raw)
    assert result.normalized_config["when"] == "First"
    assert result.normalized_config["transient"] is False


def test_parse_calgaryinput_config():
    raw = {
        "RootFileName": _field("..\\data\\Address.cydb"),
        "LinkedTables": {},
        "Query": {"text": "<And/>"},
        "CountOnly": {"attributes": {"value": "False"}},
        "SkipRecords": {"attributes": {"value": "5"}},
        "MaxRecords": {"attributes": {"value": "0"}},
    }
    result = parse_calgaryinput_config(raw)
    assert result.normalized_config["root_file_name"].endswith("Address.cydb")
    assert result.normalized_config["skip_records"] == 5
    assert result.normalized_config["max_records"] == 0
    assert result.normalized_config["query"]["text"] == "<And/>"


def test_ml_parser_automl():
    raw = {
        "target_variable": _field("price"),
        "problem_type": _field("Regression"),
        "objective_function": _field("r2"),
        "model_families": [{"text": "xgboost"}, {"text": "linear_model"}],
        "max_pipelines_search": _field("5"),
        "data_checks": _field("false"),
    }
    result = make_ml_parser("AutoML")(raw)
    assert result.normalized_config["target_variable"] == "price"
    assert result.normalized_config["model_families"] == ["xgboost", "linear_model"]
    assert result.normalized_config["max_pipelines_search"] == 5
    assert result.normalized_config["data_checks"] is False


def test_ml_parser_fit_classes_list():
    raw = {
        "schemaID": _field("Tools.Fit.2"),
        "classes_": [{"text": "Iris-setosa"}, {"text": "Iris-virginica"}],
        "DesignerVersion": _field("2020.2.0.29326"),
        "modelID": {},
        "fitToolID": {},
    }
    result = make_ml_parser("Fit")(raw)
    assert result.normalized_config["classes"] == ["Iris-setosa", "Iris-virginica"]


def test_catalog_parser_is_lossless_and_typed():
    raw = {
        "Mode": _field("encode"),
        "IncludeCrop": _field("false"),
        "Count": _field("32"),
        "Ratio": _field("0.5"),
        "Nested": {"Child": _field("v"), "attributes": {"id": "9"}},
    }
    result = parse_catalog_config(raw)
    assert result.normalized_config["Mode"] == "encode"
    assert result.normalized_config["IncludeCrop"] is False
    assert result.normalized_config["Count"] == 32
    assert result.normalized_config["Ratio"] == 0.5
    assert result.normalized_config["Nested"]["Child"] == "v"
    assert result.normalized_config["Nested"]["@attributes"]["id"] == 9


def test_catalog_parser_preserves_every_key():
    raw = {"A": _field("1"), "B": {}, "C": {"D": _field("x")}}
    result = parse_catalog_config(raw)
    assert set(result.normalized_config) == {"A", "B", "C"}
    assert result.normalized_config["C"]["D"] == "x"
