from pathlib import Path
from xml.etree import ElementTree

import pandas as pd
import pytest

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.tools.action import action_tool
from alteryx2python.tools.appendfields import appendfields_tool
from alteryx2python.tools.autofield import autofield_tool
from alteryx2python.tools.blobconvert import blobconvert_tool
from alteryx2python.tools.buffer import buffer_tool
from alteryx2python.tools.canvas import controlcontainer_tool
from alteryx2python.tools.condition import condition_tool
from alteryx2python.tools.createpoints import createpoints_tool
from alteryx2python.tools.datacleansepro import datacleansepro_tool
from alteryx2python.tools.dbfileinput import dbfileinput_tool
from alteryx2python.tools.datetime import datetime_tool
from alteryx2python.tools.datetimenow import datetimenow_tool
from alteryx2python.tools.distance import distance_tool
from alteryx2python.tools.directory import directory_tool
from alteryx2python.tools.dynamicselect import dynamicselect_tool
from alteryx2python.tools.error import error_tool
from alteryx2python.tools.fieldinfo import fieldinfo_tool
from alteryx2python.tools.filter import filter_tool
from alteryx2python.tools.findnearest import findnearest_tool
from alteryx2python.tools.findreplace import findreplace_tool
from alteryx2python.tools.formula import formula_tool
from alteryx2python.tools.generaterows import generaterows_tool
from alteryx2python.tools.interface import numericupdown_tool
from alteryx2python.tools.joinmultiple import joinmultiple_tool
from alteryx2python.tools.jsonparse import jsonparse_tool
from alteryx2python.tools.makecolumns import makecolumns_tool
from alteryx2python.tools.mapinput import mapinput_tool
from alteryx2python.tools.multifieldformula import multifieldformula_tool
from alteryx2python.tools.multirowformula import multirowformula_tool
from alteryx2python.tools.pearsoncorrelation import pearsoncorrelation_tool
from alteryx2python.tools.polybuild import polybuild_tool
from alteryx2python.tools.recordid import recordid_tool
from alteryx2python.tools.rank import rank_tool
from alteryx2python.tools.regex import regex_tool
from alteryx2python.tools.reporting import portfoliocomposertable_tool, reportmap_tool
from alteryx2python.tools.registry import TOOL_REGISTRY
from alteryx2python.tools.runningtotal import runningtotal_tool
from alteryx2python.tools.sample import sample_tool
from alteryx2python.tools.spatialinfo import spatialinfo_tool
from alteryx2python.tools.spatialmatch import spatialmatch_tool
from alteryx2python.tools.texttocolumns import texttocolumns_tool
from alteryx2python.tools.tile import tile_tool
from alteryx2python.tools.tradearea import tradearea_tool
from alteryx2python.tools.unique import unique_tool
from alteryx2python.tools.summarize import summarize_tool
from alteryx2python.tools.test import test_tool as run_test_tool
from alteryx2python.tools.xmlparse import xmlparse_tool


SAMPLES = Path("D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time")


def test_one_tool_samples_parse_supported_tool_configs():
    parser = XmlWorkflowParser()
    sample_paths = [
        SAMPLES / "01 In Out" / "DateTimeNow.yxmd",
        SAMPLES / "01 In Out" / "Directory.yxmd",
        SAMPLES / "01 In Out" / "Map_Input.yxmd",
        SAMPLES / "02 Preparation" / "Formula.yxmd",
        SAMPLES / "02 Preparation" / "Filter.yxmd",
        SAMPLES / "02 Preparation" / "Record_ID.yxmd",
        SAMPLES / "02 Preparation" / "Auto_Field.yxmd",
        SAMPLES / "02 Preparation" / "Data_CleansePro.yxmd",
        SAMPLES / "02 Preparation" / "Rank.yxmd",
        SAMPLES / "02 Preparation" / "Sample.yxmd",
        SAMPLES / "02 Preparation" / "Unique.yxmd",
        SAMPLES / "02 Preparation" / "Multi-Field_Formula.yxmd",
        SAMPLES / "02 Preparation" / "Multi-Row_Formula.yxmd",
        SAMPLES / "02 Preparation" / "Generate_Rows.yxmd",
        SAMPLES / "02 Preparation" / "Tile.yxmd",
        SAMPLES / "03 Join" / "Append.yxmd",
        SAMPLES / "03 Join" / "Find_Replace.yxmd",
        SAMPLES / "03 Join" / "Join_Multiple.yxmd",
        SAMPLES / "04 Parse" / "Text_To_Columns.yxmd",
        SAMPLES / "04 Parse" / "DateTime.yxmd",
        SAMPLES / "04 Parse" / "RegEx.yxmd",
        SAMPLES / "04 Parse" / "XML_Parse.yxmd",
        SAMPLES / "05 Transform" / "Make Columns.yxmd",
        SAMPLES / "05 Transform" / "Running_Total.yxmd",
        SAMPLES / "05 Transform" / "Summarize.yxmd",
        SAMPLES / "07 Reporting" / "Table.yxmd",
        SAMPLES / "07 Reporting" / "Report_Map.yxmd",
        SAMPLES / "07 Reporting" / "Report_Header.yxmd",
        SAMPLES / "07 Reporting" / "Report_Footer.yxmd",
        SAMPLES / "07 Reporting" / "Map_Legend_Splitter_Builder.yxmd",
        SAMPLES / "07 Reporting" / "Interactive_Chart.yxmd",
        SAMPLES / "09 Spatial" / "Create_Points.yxmd",
        SAMPLES / "09 Spatial" / "Buffer.yxmd",
        SAMPLES / "09 Spatial" / "Distance.yxmd",
        SAMPLES / "09 Spatial" / "Find_Nearest.yxmd",
        SAMPLES / "09 Spatial" / "Poly-Split Build.yxmd",
        SAMPLES / "09 Spatial" / "Spatial_Info.yxmd",
        SAMPLES / "09 Spatial" / "Spatial_Match.yxmd",
        SAMPLES / "09 Spatial" / "Trade_Area.yxmd",
        SAMPLES / "10 Interface" / "Error_Message.yxwz",
        SAMPLES / "10 Interface" / "Action.yxwz",
        SAMPLES / "10 Interface" / "Condition.yxwz",
        SAMPLES / "10 Interface" / "Check_Box.yxwz",
        SAMPLES / "10 Interface" / "Drop_Down.yxwz",
        SAMPLES / "10 Interface" / "File_Browse.yxwz",
        SAMPLES / "10 Interface" / "List_Box.yxwz",
        SAMPLES / "10 Interface" / "Numeric_Up_Down.yxwz",
        SAMPLES / "10 Interface" / "Radio_Button.yxwz",
        SAMPLES / "10 Interface" / "Text_Box.yxwz",
        SAMPLES / "11 Data Investigation" / "Pearson_Correlation.yxmd",
        SAMPLES / "22 Developer" / "Dynamic_Select.yxmd",
        SAMPLES / "22 Developer" / "Field_Info.yxmd",
        SAMPLES / "22 Developer" / "Blob_Convert.yxmd",
        SAMPLES / "22 Developer" / "JSON_Parse.yxmd",
        SAMPLES / "22 Developer" / "Test.yxmd",
        SAMPLES / "22 Developer" / "ControlContainer.yxmd",
    ]

    workflows = [parser.parse(path) for path in sample_paths]
    parsed_tool_types = {
        node.tool_type
        for workflow in workflows
        for node in workflow.nodes
        if node.tool_type in {
            "AppendFields",
            "Action",
            "AutoField",
            "BlobConvert",
            "Buffer",
            "Condition",
            "ControlContainer",
            "CreatePoints",
            "DataCleansePro",
            "Distance",
            "DateTimeNow",
            "Directory",
            "DynamicSelect",
            "Error",
            "FieldInfo",
            "FindReplace",
            "FindNearest",
            "Formula",
            "Filter",
            "GenerateRows",
            "DropDown",
            "JoinMultiple",
            "Label",
            "LabelGroup",
            "ListBox",
            "JSONParse",
            "MakeColumns",
            "MapInput",
            "MultiFieldFormula",
            "MultiRowFormula",
            "NumericUpDown",
            "PearsonCorrelation",
            "PlotlyCharting",
            "PolyBuild",
            "PortfolioComposerTable",
            "QuestionFileBrowse",
            "QuestionTab",
            "QuestionTextBox",
            "RadioButtonGroup",
            "RecordID",
            "Rank",
            "RegEx",
            "ReportMap",
            "ReportFooter",
            "ReportHeader",
            "ReportLegendBuilder",
            "ReportLegendSplitter",
            "RunningTotal",
            "Sample",
            "Summarize",
            "SpatialInfo",
            "SpatialMatch",
            "Test",
            "TextToColumns",
            "Tile",
            "TradeArea",
            "Unique",
            "DateTime",
            "XMLParse",
        }
    }

    assert parsed_tool_types == {
        "AppendFields",
        "Action",
        "AutoField",
        "BlobConvert",
        "Buffer",
        "Condition",
        "ControlContainer",
        "CreatePoints",
        "DataCleansePro",
        "Distance",
        "DateTimeNow",
        "Directory",
        "DynamicSelect",
        "Error",
        "FieldInfo",
        "FindReplace",
        "FindNearest",
        "Formula",
        "Filter",
        "GenerateRows",
        "DropDown",
        "JoinMultiple",
        "Label",
        "LabelGroup",
        "ListBox",
        "JSONParse",
        "MakeColumns",
        "MapInput",
        "MultiFieldFormula",
        "MultiRowFormula",
        "NumericUpDown",
        "PearsonCorrelation",
        "PlotlyCharting",
        "PolyBuild",
        "PortfolioComposerTable",
        "QuestionFileBrowse",
        "QuestionTab",
        "QuestionTextBox",
        "RadioButtonGroup",
        "RecordID",
        "Rank",
        "RegEx",
        "ReportMap",
        "ReportFooter",
        "ReportHeader",
        "ReportLegendBuilder",
        "ReportLegendSplitter",
        "RunningTotal",
        "Sample",
        "Summarize",
        "SpatialInfo",
        "SpatialMatch",
        "Test",
        "TextToColumns",
        "Tile",
        "TradeArea",
        "Unique",
        "DateTime",
        "XMLParse",
    }
    for tool_type in parsed_tool_types:
        assert tool_type in TOOL_REGISTRY.list_tool_types()


def _parse_sample(path: Path):
    return XmlWorkflowParser().parse(path)


def _node_config(workflow, tool_type: str, predicate=None):
    for node in workflow.nodes:
        if node.tool_type != tool_type:
            continue
        normalized = node.config["normalized"]
        if predicate is None or predicate(normalized):
            return normalized
    raise AssertionError(f"No matching {tool_type} node found")


def _text_input_frame(path: Path, tool_id: str) -> pd.DataFrame:
    root = ElementTree.fromstring(path.read_bytes())
    node = root.find(f".//Node[@ToolID='{tool_id}']")
    assert node is not None
    fields = [
        field.attrib["name"]
        for field in node.findall("./Properties/Configuration/Fields/Field")
    ]
    rows = []
    for row in node.findall("./Properties/Configuration/Data/r"):
        rows.append([cell.text or "" for cell in row.findall("c")])
    return pd.DataFrame(rows, columns=fields)


def test_json_parse_sample_config_executes_against_embedded_text_input():
    path = SAMPLES / "22 Developer" / "JSON_Parse.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "JSONParse", lambda cfg: cfg["single_field"] is True)
    frame = _text_input_frame(path, "5")

    output = jsonparse_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert {"JSON_Name", "JSON_ValueString"} == set(output.columns)
    assert {"firstName", "address.city", "phoneNumber.0.number"}.issubset(set(output["JSON_Name"]))
    assert output.loc[output["JSON_Name"] == "address.city", "JSON_ValueString"].item() == "New York"


def test_controlcontainer_sample_config_executes_as_structural_noop():
    path = SAMPLES / "22 Developer" / "ControlContainer.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "ControlContainer", lambda cfg: cfg.get("caption") == "Basics")

    result = controlcontainer_tool({}, config, WorkflowContext())

    assert result == {}


def test_test_sample_config_executes_expression_check_against_small_frame():
    path = SAMPLES / "22 Developer" / "Test.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "Test", lambda cfg: cfg["tests"][0]["type"] == "ExpAll")

    result = run_test_tool({"Input": pd.DataFrame({"LOCNUM": [2, 3]})}, config, WorkflowContext())

    assert result == {}


def test_error_message_sample_config_records_without_enforcing():
    path = SAMPLES / "10 Interface" / "Error_Message.yxwz"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "Error")

    result = error_tool(
        {"Input": pd.DataFrame({"#1": [True]})},
        config,
        WorkflowContext(),
    )

    assert result == {}
    assert config["expression"] == "[#1]"
    assert "Check Box was enabled" in config["message"]


def test_numeric_up_down_sample_config_emits_question_payload():
    path = SAMPLES / "10 Interface" / "Numeric_Up_Down.yxwz"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "NumericUpDown")

    output = numericupdown_tool({}, config, WorkflowContext())["Question"]

    assert output.loc[0, "tool_type"] == "NumericUpDown"
    assert output.loc[0, "value"] == "Adjust the value to a number between 0 and 100"


def test_condition_sample_config_emits_branch_payloads():
    path = SAMPLES / "10 Interface" / "Condition.yxwz"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "Condition")

    outputs = condition_tool(
        {"Question": pd.DataFrame([{"value": "True"}])},
        config,
        WorkflowContext(),
    )

    assert bool(outputs["True Condition"].loc[0, "active"]) is True
    assert bool(outputs["False Condition"].loc[0, "active"]) is False


def test_action_sample_config_emits_action_payload():
    path = SAMPLES / "10 Interface" / "Action.yxwz"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "Action")

    outputs = action_tool(
        {"Question": pd.DataFrame([{"tool_type": "QuestionTextBox", "value": "sample"}])},
        config,
        WorkflowContext(),
    )

    assert set(outputs) == {"Action"}
    assert bool(outputs["Action"].loc[0, "active"]) is True


def test_record_id_sample_configs_execute_against_embedded_text_input():
    path = SAMPLES / "02 Preparation" / "Record_ID.yxmd"
    workflow = _parse_sample(path)
    frame = _text_input_frame(path, "123")

    first_config = _node_config(workflow, "RecordID", lambda cfg: cfg["field_name"] == "Record ID")
    first_output = recordid_tool({"Input": frame}, first_config, WorkflowContext())["Output"]
    assert list(first_output.columns)[0] == "Record ID"
    assert first_output["Record ID"].tolist() == list(range(1, len(frame.index) + 1))

    last_config = _node_config(workflow, "RecordID", lambda cfg: cfg["field_name"] == "Record ID Last Column")
    last_output = recordid_tool({"Input": frame}, last_config, WorkflowContext())["Output"]
    assert list(last_output.columns)[-1] == "Record ID Last Column"
    assert last_output["Record ID Last Column"].tolist()[:3] == [-100, -99, -98]

    grouped_config = _node_config(workflow, "RecordID", lambda cfg: cfg["field_name"] == "Grouped Record ID")
    grouped_output = recordid_tool({"Input": frame}, grouped_config, WorkflowContext())["Output"]
    assert grouped_output.groupby("Region")["Grouped Record ID"].min().tolist() == [1, 1, 1, 1]


def test_filter_sample_config_executes_against_embedded_text_input():
    path = SAMPLES / "02 Preparation" / "Filter.yxmd"
    workflow = _parse_sample(path)
    frame = _text_input_frame(path, "155")
    frame["CustomerID"] = frame["CustomerID"].astype(int)
    config = _node_config(workflow, "Filter", lambda cfg: cfg["expression"] == "[CustomerID] > 30")

    output = filter_tool({"Input": frame}, config, WorkflowContext())

    assert output["True"]["CustomerID"].tolist() == [49, 456, 31]
    assert output["False"]["CustomerID"].tolist() == [5, 1, 2]


def test_formula_sample_config_executes_supported_formula_from_workflow():
    path = SAMPLES / "02 Preparation" / "Formula.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(
        workflow,
        "Formula",
        lambda cfg: cfg["formula_fields"][0]["field"] == "RecordSource",
    )
    frame = pd.DataFrame({"City": ["new york"], "Latitude": [40.1], "Spend": [10.0], "Visits": [2]})

    output = formula_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert output["RecordSource"].tolist() == ["Alteryx Sample Data"]


def test_unique_sample_config_executes_against_small_frame():
    path = SAMPLES / "02 Preparation" / "Unique.yxmd"
    workflow = _parse_sample(path)
    frame = pd.DataFrame(
        {
            "FirstName": ["Ada", "Ada", "Grace"],
            "LastName": ["Lovelace", "Lovelace", "Hopper"],
            "Address": ["A", "B", "C"],
        }
    )
    config = _node_config(workflow, "Unique", lambda cfg: cfg["unique_fields"] == ["FirstName", "LastName"])

    outputs = unique_tool({"Input": frame}, config, WorkflowContext())

    assert len(outputs["Unique"].index) < len(frame.index)
    assert len(outputs["Duplicates"].index) > 0


def test_sample_sample_config_executes_against_small_frame():
    path = SAMPLES / "02 Preparation" / "Sample.yxmd"
    workflow = _parse_sample(path)
    frame = pd.DataFrame({"City": ["A", "A", "B", "B"], "value": [1, 2, 3, 4]})
    config = _node_config(workflow, "Sample", lambda cfg: cfg["mode"] == "First" and cfg["n"] == 3)

    output = sample_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert len(output.index) == 3
    assert output.to_dict("records") == frame.head(3).to_dict("records")


def test_findreplace_sample_config_executes_against_embedded_text_inputs():
    path = SAMPLES / "03 Join" / "Find_Replace.yxmd"
    workflow = _parse_sample(path)
    targets = _text_input_frame(path, "171")
    source = _text_input_frame(path, "258")
    config = _node_config(workflow, "FindReplace", lambda cfg: cfg["field_search"] == "word")

    output = findreplace_tool({"Targets": targets, "Source": source}, config, WorkflowContext())["Output"]

    assert output.loc[0, "acct_holder"] == "GLEN AND ALLENS HARDWARE COMPANY"


def test_texttocolumns_sample_config_executes_against_small_frame():
    path = SAMPLES / "04 Parse" / "Text_To_Columns.yxmd"
    workflow = _parse_sample(path)
    frame = pd.DataFrame({"Address": ["123 Main,New York,NY"]})
    config = _node_config(workflow, "TextToColumns", lambda cfg: cfg["field"] == "Address")

    output = texttocolumns_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert {"Address1", "Address2", "Address3"}.issubset(output.columns)


def test_multifieldformula_sample_config_executes_against_small_frame():
    path = SAMPLES / "02 Preparation" / "Multi-Field_Formula.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "MultiFieldFormula", lambda cfg: cfg["copy_output"] is False)
    frame = pd.DataFrame({"NAME": ["alice"], "ADDRESS": ["main"], "CITY": ["new york"], "STATE": ["ny"], "ZIP": ["10001"]})

    output = multifieldformula_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert output.loc[0, "NAME"] == "ALICE"
    assert output.loc[0, "CITY"] == "NEW YORK"


def test_multirowformula_sample_config_executes_against_small_frame():
    path = SAMPLES / "02 Preparation" / "Multi-Row_Formula.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "MultiRowFormula", lambda cfg: cfg["create_field_name"] == "RecordID")
    frame = pd.DataFrame({"Product": ["A", "A", "B"], "Year": [2024, 2025, 2024]})

    output = multirowformula_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert output["RecordID"].tolist() == [1, 2, 1]


def test_pearsoncorrelation_sample_config_executes_against_embedded_text_input():
    path = SAMPLES / "11 Data Investigation" / "Pearson_Correlation.yxmd"
    workflow = _parse_sample(path)
    frame = _text_input_frame(path, "29")
    config = _node_config(
        workflow,
        "PearsonCorrelation",
        lambda cfg: cfg["fields"] == ["Years of education", "Salary"] and cfg["covariance"] is False,
    )

    output = pearsoncorrelation_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert output.to_dict("records") == [
        {
            "Field1": "Years of education",
            "Field2": "Salary",
            "Correlation": pytest.approx(0.8958904118, rel=1e-6),
        }
    ]


def test_reporting_sample_configs_emit_report_fragments():
    table_path = SAMPLES / "07 Reporting" / "Table.yxmd"
    table_workflow = _parse_sample(table_path)
    table_config = _node_config(table_workflow, "PortfolioComposerTable", lambda cfg: cfg["table_mode"] == "Basic")
    table_output = portfoliocomposertable_tool(
        {"Input": pd.DataFrame({"City": ["New York"], "Total Sales": [100]})},
        table_config,
        WorkflowContext(),
    )["Output"]

    assert table_output.loc[0, "report_type"] == "PortfolioComposerTable"
    assert table_output.loc[0, "source_columns"] == ["City", "Total Sales"]

    map_path = SAMPLES / "07 Reporting" / "Report_Map.yxmd"
    map_workflow = _parse_sample(map_path)
    map_config = _node_config(map_workflow, "ReportMap")
    map_output = reportmap_tool(
        {"Input": pd.DataFrame({"Centroid": ["POINT (-73 40)"]})},
        map_config,
        WorkflowContext(),
    )["Output"]

    assert map_output.loc[0, "report_type"] == "ReportMap"


def test_mapinput_sample_config_emits_embedded_spatial_rows():
    path = SAMPLES / "01 In Out" / "Map_Input.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "MapInput", lambda cfg: len(cfg["rows"]) == 1)

    output = mapinput_tool({}, config, WorkflowContext())["Output"]

    assert output.loc[0, "Label"] == "Alteryx (Colorado Office)"
    assert output.loc[0, "SpatialObj"] == "POINT (-105.10751 39.915645)"


def test_createpoints_sample_config_executes_against_small_frame():
    path = SAMPLES / "09 Spatial" / "Create_Points.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "CreatePoints", lambda cfg: cfg["x_field"] == "Lon")

    output = createpoints_tool(
        {"Input": pd.DataFrame({"Name": ["Empire State"], "Lon": [-73.9857], "Lat": [40.7484]})},
        config,
        WorkflowContext(),
    )["Output"]

    assert output.loc[0, "Centroid"] == "POINT (-73.9857 40.7484)"


def test_buffer_sample_config_executes_against_wkt_polygon():
    path = SAMPLES / "09 Spatial" / "Buffer.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "Buffer", lambda cfg: cfg["buffer_size"] == "1")

    output = buffer_tool(
        {
            "Input": pd.DataFrame(
                {"SpatialObject_TradeArea": ["POLYGON ((0 1, 1 1, 1 0, 0 0, 0 1))"]}
            )
        },
        {**config, "buffer_size": "69"},
        WorkflowContext(),
    )["Output"]

    assert output.loc[0, "SpatialObj_Buffer"] == "POLYGON ((-1 2, 2 2, 2 -1, -1 -1, -1 2))"


def test_distance_sample_config_executes_against_wkt_points():
    path = SAMPLES / "09 Spatial" / "Distance.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "Distance", lambda cfg: cfg["output_direction_degrees"] is True)

    output = distance_tool(
        {
            "Input": pd.DataFrame(
                {
                    "Customer Point": ["POINT (0 0)"],
                    "Store Point": ["POINT (1 1)"],
                }
            )
        },
        config,
        WorkflowContext(),
    )["Output"]

    assert output.loc[0, "DistanceMiles"] == pytest.approx(97.71, rel=1e-3)
    assert output.loc[0, "Direction"] == "NE"
    assert output.loc[0, "DirectionDegrees"] == pytest.approx(44.9956, rel=1e-4)


def test_findnearest_sample_config_executes_against_wkt_points():
    path = SAMPLES / "09 Spatial" / "Find_Nearest.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "FindNearest", lambda cfg: cfg["max_distance_units"] == "Miles")

    output = findnearest_tool(
        {
            "Targets": pd.DataFrame({"Store Point": ["POINT (0 0)"]}),
            "Universe": pd.DataFrame({"Name": ["Near", "Far"], "SpatialObj": ["POINT (0.1 0)", "POINT (9 0)"]}),
        },
        config,
        WorkflowContext(),
    )["Matched"]

    assert output.loc[0, "Universe_Name"] == "Near"
    assert output.loc[0, "FindNearestRank"] == 1
    assert output.loc[0, "DistanceMiles"] == pytest.approx(6.909, rel=1e-3)


def test_polybuild_sample_config_executes_sequence_polygon():
    path = SAMPLES / "09 Spatial" / "Poly-Split Build.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "PolyBuild", lambda cfg: cfg["build_type"] == "SequencePolygon")

    output = polybuild_tool(
        {
            "Input": pd.DataFrame(
                {
                    "Store Num": ["A", "A", "A"],
                    "Split_SequenceNum": [3, 1, 2],
                    "Split_SpatialObj": ["POINT (0 1)", "POINT (0 0)", "POINT (1 0)"],
                }
            )
        },
        config,
        WorkflowContext(),
    )["Output"]

    assert output.loc[0, "Store Num"] == "A"
    assert output.loc[0, "SpatialObj_Built"] == "POLYGON ((0 0, 1 0, 0 1, 0 0))"


def test_spatialinfo_sample_config_executes_area_against_wkt_polygon():
    path = SAMPLES / "09 Spatial" / "Spatial_Info.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "SpatialInfo", lambda cfg: cfg["selected_items"] == ["AreaMi"])

    output = spatialinfo_tool(
        {"Input": pd.DataFrame({"SpatialObj": ["POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))"]})},
        config,
        WorkflowContext(),
    )["Output"]

    assert output.loc[0, "AreaSqMi"] == 4.0


def test_tradearea_sample_config_executes_radius_ranges_against_wkt_point():
    path = SAMPLES / "09 Spatial" / "Trade_Area.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "TradeArea", lambda cfg: cfg["radii"] == "2-5, 7-10")

    output = tradearea_tool(
        {"Input": pd.DataFrame({"Store Point": ["POINT (-105 40)"]})},
        config,
        WorkflowContext(),
    )["Output"]

    assert output["RadiusSize"].tolist() == ["2-5", "7-10"]
    assert output["SpatialObject_TradeArea"].str.startswith("POLYGON ((").all()


def test_spatialmatch_sample_config_executes_contains_against_wkt_frames():
    path = SAMPLES / "09 Spatial" / "Spatial_Match.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "SpatialMatch", lambda cfg: cfg["method"] == "Contains")

    output = spatialmatch_tool(
        {
            "Targets": pd.DataFrame({"SpatialObject_TradeArea": ["POLYGON ((0 3, 3 3, 3 0, 0 0, 0 3))"]}),
            "Universe": pd.DataFrame({"SpatialObj": ["POINT (1 1)", "POINT (9 9)"]}),
        },
        config,
        WorkflowContext(),
    )["Matched"]

    assert len(output.index) == 1
    assert output.loc[0, "Target_SpatialObject_TradeArea"].startswith("POLYGON")


def test_appendfields_sample_config_executes_against_small_frames():
    path = SAMPLES / "03 Join" / "Append.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "AppendFields", lambda cfg: cfg["cartesian_mode"] == "Allow")

    output = appendfields_tool(
        {"Targets": pd.DataFrame({"id": [1]}), "Source": pd.DataFrame({"label": ["A", "B"]})},
        config,
        WorkflowContext(),
    )["Output"]

    assert output["label"].tolist() == ["A", "B"]


def test_autofield_sample_config_executes_against_small_frame():
    path = SAMPLES / "02 Preparation" / "Auto_Field.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "AutoField")

    output = autofield_tool(
        {"Input": pd.DataFrame({"State": ["1", "2"], "City": ["A", "B"]})},
        config,
        WorkflowContext(),
    )["Output"]

    assert str(output["State"].dtype) == "Int64"


def test_datacleansepro_sample_config_executes_against_small_frame():
    path = SAMPLES / "02 Preparation" / "Data_CleansePro.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "DataCleansePro", lambda cfg: cfg["case_mode"] == "upper")

    output = datacleansepro_tool(
        {"Input": pd.DataFrame({"Region": [" west "], "Score": [None]})},
        config,
        WorkflowContext(),
    )["Output"]

    assert output.loc[0, "Region"] == "WEST"


def test_runningtotal_sample_config_executes_against_small_frame():
    path = SAMPLES / "05 Transform" / "Running_Total.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "RunningTotal", lambda cfg: cfg["group_by_fields"] == ["City"])

    output = runningtotal_tool(
        {"Input": pd.DataFrame({"City": ["A", "A", "B"], "Spend": [2, 3, 4]})},
        config,
        WorkflowContext(),
    )["Output"]

    assert output["RunningTotal_Spend"].tolist() == [2, 5, 4]


def test_summarize_sample_config_executes_against_small_frame():
    path = SAMPLES / "05 Transform" / "Summarize.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "Summarize", lambda cfg: any(field["action"] == "Sum" for field in cfg["summarize_fields"]))

    output = summarize_tool(
        {
            "Input": pd.DataFrame(
                {"State": ["NY", "NY", "CA"], "City": ["A", "A", "B"], "Visits": [1, 3, 5], "Spend": [10, 20, 7]}
            )
        },
        config,
        WorkflowContext(),
    )["Output"]

    assert output.loc[0, "Sum_Spend"] == 30


def test_fieldinfo_sample_config_executes_against_small_frame():
    path = SAMPLES / "22 Developer" / "Field_Info.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "FieldInfo")

    output = fieldinfo_tool({"Input": pd.DataFrame({"Name": ["Ada"], "Spend": [1.0]})}, config, WorkflowContext())["Output"]

    assert output["Name"].tolist() == ["Name", "Spend"]


def test_dynamicselect_sample_config_executes_against_small_frame():
    path = SAMPLES / "22 Developer" / "Dynamic_Select.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(
        workflow,
        "DynamicSelect",
        lambda cfg: cfg["mode"] == "FieldTypes" and "V_String" in cfg["field_types"],
    )
    frame = pd.DataFrame({"Name": pd.Series(["Ada"], dtype="string"), "Spend": [1.0]})

    output = dynamicselect_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert list(output.columns) == ["Name"]


def test_blobconvert_sample_config_executes_against_small_frame():
    path = SAMPLES / "22 Developer" / "Blob_Convert.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "BlobConvert", lambda cfg: cfg["mode"] == "Base64" and not cfg["to_blob"])

    output = blobconvert_tool(
        {"Input": pd.DataFrame({"Blob": [b"hello"]})},
        config,
        WorkflowContext(),
    )["Output"]

    assert output.loc[0, "Blob"] == "aGVsbG8="


def test_rank_sample_config_executes_against_embedded_text_input():
    path = SAMPLES / "02 Preparation" / "Rank.yxmd"
    workflow = _parse_sample(path)
    frame = _text_input_frame(path, "95")
    frame["Units Sold"] = frame["Units Sold"].astype(int)
    config = _node_config(workflow, "Rank", lambda cfg: cfg["ranking_modes"] == ["Ordinal"] and not cfg["group_fields"])

    output = rank_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert output["Rank"].head(3).tolist() == [1, 2, 3]


def test_datetime_sample_config_executes_against_embedded_text_input():
    path = SAMPLES / "04 Parse" / "DateTime.yxmd"
    workflow = _parse_sample(path)
    frame = _text_input_frame(path, "137")
    config = _node_config(workflow, "DateTime", lambda cfg: cfg["input_field_name"] == "DOB")

    output = datetime_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert output.loc[0, "DOB_New"] == "1977-01-24"


def test_regex_sample_config_executes_against_small_frame():
    path = SAMPLES / "04 Parse" / "RegEx.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "RegEx", lambda cfg: cfg["method"] == "ParseComplex" and cfg["field"] == "Name")

    output = regex_tool({"Input": pd.DataFrame({"Name": ["ada lovelace"]})}, config, WorkflowContext())["Output"]

    assert output.loc[0, "First Name"] == "ada"


def test_xmlparse_sample_config_executes_against_small_frame():
    path = SAMPLES / "04 Parse" / "XML_Parse.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "XMLParse", lambda cfg: cfg["xml_element"] == "transaction")
    frame = pd.DataFrame(
        {
            "row_id": [1],
            "customer_xml": [
                """
                <customer id="C001">
                  <transactions>
                    <transaction id="1"><date>2026-01-01</date><amount>10</amount></transaction>
                  </transactions>
                </customer>
                """
            ],
        }
    )

    output = xmlparse_tool({"Input": frame}, config, WorkflowContext())["Output"]

    assert output.loc[0, "id"] == "1"
    assert output.loc[0, "date"] == "2026-01-01"
    assert output.loc[0, "amount"] == "10"


def test_datetimenow_sample_config_executes_with_injected_clock():
    path = SAMPLES / "01 In Out" / "DateTimeNow.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "DateTimeNow")

    output = datetimenow_tool({}, {**config, "now": "2026-06-22T15:04:05"}, WorkflowContext())["Output"]

    assert output.loc[0, "DateTimeNow"] == "2026-06-22"


def test_directory_sample_config_executes_against_official_sample_dir():
    path = SAMPLES / "01 In Out" / "Directory.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "Directory", lambda cfg: cfg["file_spec"] == "*.*" and not cfg["include_subdirs"])

    output = directory_tool({}, config, WorkflowContext())["Output"]

    assert "FileName" in output.columns
    assert len(output.index) > 0


def test_generaterows_sample_config_executes_without_input():
    path = SAMPLES / "02 Preparation" / "Generate_Rows.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "GenerateRows", lambda cfg: cfg["create_field_name"] == "RowCount")

    output = generaterows_tool({}, config, WorkflowContext())["Output"]

    assert output["RowCount"].tolist() == list(range(1, 11))


def test_generaterows_datetime_sample_config_executes_against_small_frame():
    path = SAMPLES / "02 Preparation" / "Generate_Rows.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "GenerateRows", lambda cfg: cfg["create_field_name"] == "date")

    output = generaterows_tool(
        {"Input": pd.DataFrame({"accountOpenDt": ["2026-06-20"], "accountCloseDt": ["2026-06-22"]})},
        config,
        WorkflowContext(),
    )["Output"]

    assert output["date"].tolist() == ["2026-06-20", "2026-06-21", "2026-06-22"]


def test_tile_sample_config_executes_equal_records_against_small_frame():
    path = SAMPLES / "02 Preparation" / "Tile.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "Tile", lambda cfg: cfg["method"] == "EqualRecords" and not cfg.get("sort_field"))

    output = tile_tool({"Input": pd.DataFrame({"value": list(range(10))})}, config, WorkflowContext())["Output"]

    assert output["Tile_Num"].min() == 1
    assert output["Tile_Num"].max() == 5


def test_makecolumns_sample_config_executes_against_small_frame():
    path = SAMPLES / "05 Transform" / "Make Columns.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "MakeColumns", lambda cfg: cfg["num_columns"] == 3 and not cfg["group_fields"])

    output = makecolumns_tool({"Input": pd.DataFrame({"value": [1, 2, 3, 4]})}, config, WorkflowContext())["Output"]

    assert {"value_1", "value_2", "value_3"}.issubset(output.columns)


def test_joinmultiple_sample_config_executes_against_small_frames():
    path = SAMPLES / "03 Join" / "Join_Multiple.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(workflow, "JoinMultiple", lambda cfg: len(cfg["joins"]) == 3)

    output = joinmultiple_tool(
        {
            "Input": pd.DataFrame({"Name": ["Ada"], "A": [1]}),
            "Input_2": pd.DataFrame({"Name": ["Ada"], "B": [2]}),
            "Input_3": pd.DataFrame({"Name": ["Ada"], "C": [3]}),
        },
        config,
        WorkflowContext(),
    )["Output"]

    assert len(output.index) == 1
    assert output.loc[0, "Input_#2_Name"] == "Ada"


def test_input_data_sample_csv_config_executes_against_official_sample_file():
    path = SAMPLES / "01 In Out" / "Input_Data.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(
        workflow,
        "DbFileInput",
        lambda cfg: cfg["file"].endswith("State Populations.csv"),
    )
    config = {**config, "base_dir": str(path.parent)}

    output = dbfileinput_tool({}, config, WorkflowContext())["Output"]

    assert list(output.columns) == ["State", "AreaSqMi", "Average Household Size", "Total Population"]
    assert len(output.index) > 0
    assert output.iloc[0]["State"]


def test_input_data_sample_excel_named_range_is_explicitly_deferred():
    path = SAMPLES / "01 In Out" / "Input_Data.yxmd"
    workflow = _parse_sample(path)
    config = _node_config(
        workflow,
        "DbFileInput",
        lambda cfg: "NamedRangeExample" in cfg["file"],
    )
    config = {**config, "base_dir": str(path.parent)}

    with pytest.raises(NotImplementedError, match="Named ranges"):
        dbfileinput_tool({}, config, WorkflowContext())


def test_input_data_sample_csv_node_executes_through_graph_runtime():
    path = SAMPLES / "01 In Out" / "Input_Data.yxmd"
    workflow = _parse_sample(path)
    csv_node = next(
        node
        for node in workflow.nodes
        if node.tool_type == "DbFileInput"
        and node.config["normalized"]["file"].endswith("State Populations.csv")
    )
    csv_node.config["normalized"] = {**csv_node.config["normalized"], "base_dir": str(path.parent)}
    workflow.nodes = [csv_node]
    workflow.edges = []

    result = run_workflow_graph(workflow, WorkflowContext())

    output = result.node_results[csv_node.node_id].outputs["Output"]
    assert result.execution_order == [csv_node.node_id]
    assert list(output.columns) == ["State", "AreaSqMi", "Average Household Size", "Total Population"]
