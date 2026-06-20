from pathlib import Path
from xml.etree import ElementTree

import pandas as pd
import pytest

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.tools.dbfileinput import dbfileinput_tool
from alteryx2python.tools.filter import filter_tool
from alteryx2python.tools.formula import formula_tool
from alteryx2python.tools.jsonparse import jsonparse_tool
from alteryx2python.tools.recordid import recordid_tool
from alteryx2python.tools.registry import TOOL_REGISTRY


SAMPLES = Path("D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time")


def test_one_tool_samples_parse_supported_tool_configs():
    parser = XmlWorkflowParser()
    sample_paths = [
        SAMPLES / "02 Preparation" / "Formula.yxmd",
        SAMPLES / "02 Preparation" / "Filter.yxmd",
        SAMPLES / "02 Preparation" / "Record_ID.yxmd",
        SAMPLES / "22 Developer" / "JSON_Parse.yxmd",
    ]

    workflows = [parser.parse(path) for path in sample_paths]
    parsed_tool_types = {
        node.tool_type
        for workflow in workflows
        for node in workflow.nodes
        if node.tool_type in {"Formula", "Filter", "RecordID", "JSONParse"}
    }

    assert parsed_tool_types == {"Formula", "Filter", "RecordID", "JSONParse"}
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
