import pandas as pd
import pytest

from alteryx2python.tools.dbfileinput import DbFileInputTool, dbfileinput_tool


def test_dbfileinput_reads_csv_from_configured_file(workflow_context):
    result = dbfileinput_tool(
        {},
        {
            "node_id": "input-1",
            "file": "tests/fixtures/input_data_basic.csv",
            "file_attributes": {"FileFormat": "0"},
            "format_specific_options": {
                "HeaderRow": {"attributes": {"value": "True"}},
                "Delimeter": {"text": ","},
                "ImportLine": {"text": "1"},
            },
        },
        workflow_context,
    )

    output = result["Output"]
    assert output.to_dict("records") == [
        {"name": "alpha", "amount": 10},
        {"name": "beta", "amount": 20},
        {"name": "gamma", "amount": 30},
    ]
    trace = workflow_context.traces[-1].to_dict()
    assert trace["outputs"]["Output"]["row_count"] == 3
    assert trace["outputs"]["Output"]["columns"] == ["name", "amount"]


def test_dbfileinput_applies_record_limit_and_import_line(workflow_context):
    result = dbfileinput_tool(
        {},
        {
            "file": "tests/fixtures/input_data_offset.csv",
            "file_attributes": {"FileFormat": "0", "RecordLimit": "2"},
            "format_specific_options": {
                "HeaderRow": {"attributes": {"value": "True"}},
                "Delimeter": {"text": ","},
                "ImportLine": {"text": "3"},
            },
        },
        workflow_context,
    )

    output = result["Output"]
    assert output.to_dict("records") == [
        {"name": "alpha", "amount": 10},
        {"name": "beta", "amount": 20},
    ]


def test_dbfileinput_resolves_alteryx_suffix_and_base_dir(workflow_context, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "input.csv"
    csv_path.write_text("name,amount\nalpha,10\n", encoding="utf-8")

    result = dbfileinput_tool(
        {},
        {
            "file": "data/input.csv|||ignored",
            "base_dir": str(tmp_path),
            "file_attributes": {"FileFormat": "0"},
            "format_specific_options": {"HeaderRow": {"attributes": {"value": "True"}}},
        },
        workflow_context,
    )

    assert result["Output"].to_dict("records") == [{"name": "alpha", "amount": 10}]


def test_dbfileinput_reads_excel_sheet_with_header_row(workflow_context):
    result = dbfileinput_tool(
        {},
        {
            "file": "D:/Alteryx/Samples/data/StartHereData/Excel.CustomerLocationData.xlsx|||`Customers$`",
            "file_attributes": {"FileFormat": "25"},
            "format_specific_options": {"FirstRowData": {"text": "False"}, "ImportLine": {"text": "1"}},
        },
        workflow_context,
    )

    output = result["Output"]
    assert output.columns[:3].tolist() == ["CustomerID", "First Name", "Last Name"]
    assert output.iloc[0][["CustomerID", "First Name", "Last Name"]].to_dict() == {
        "CustomerID": 2,
        "First Name": "JEAN",
        "Last Name": "SMITH",
    }


def test_dbfileinput_reads_excel_sheet_without_header_row_as_f_fields(workflow_context):
    result = dbfileinput_tool(
        {},
        {
            "file": "D:/Alteryx/Samples/data/StartHereData/Excel.CustomerResponderData.xlsx|||`Sheet1$`",
            "file_attributes": {"FileFormat": "25"},
            "format_specific_options": {"FirstRowData": {"text": "True"}, "ImportLine": {"text": "1"}},
        },
        workflow_context,
    )

    output = result["Output"]
    assert output.columns.tolist() == ["F1", "F2", "F3", "F4"]
    assert output.iloc[0].to_dict() == {"F1": 2, "F2": 100, "F3": "Corporate", "F4": "No"}


@pytest.mark.parametrize(
    "file_value",
    [
        "tests/fixtures/input_data_basic.yxdb",
        "tests/fixtures/input_data_basic.xlsx|||`NamedRangeExample`",
        "tests/fixtures/input_data_basic.xlsx|||<List of Sheet Names>",
    ],
)
def test_dbfileinput_rejects_deferred_sources(file_value, workflow_context):
    with pytest.raises(NotImplementedError):
        dbfileinput_tool(
            {},
            {"file": file_value, "file_attributes": {"FileFormat": "19"}, "format_specific_options": {}},
            workflow_context,
        )


def test_dbfileinput_tool_class_executes_same_contract(workflow_context):
    tool = DbFileInputTool()

    result = tool.execute(
        {},
        {
            "file": "tests/fixtures/input_data_basic.csv",
            "file_attributes": {"FileFormat": "0"},
            "format_specific_options": {"HeaderRow": {"attributes": {"value": "True"}}},
        },
        workflow_context,
    )

    assert isinstance(result["Output"], pd.DataFrame)
