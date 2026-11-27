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


def test_dbfileinput_reads_excel_sheet_with_header_row(workflow_context, tmp_path):
    workbook = tmp_path / "customers.xlsx"
    pd.DataFrame({"CustomerID": [2], "First Name": ["JEAN"], "Last Name": ["SMITH"]}).to_excel(
        workbook, sheet_name="Customers", index=False
    )
    result = dbfileinput_tool(
        {},
        {
            "file": f"{workbook}|||`Customers$`",
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


def test_dbfileinput_reads_excel_sheet_without_header_row_as_f_fields(workflow_context, tmp_path):
    workbook = tmp_path / "responders.xlsx"
    pd.DataFrame([[2, 100, "Corporate", "No"]]).to_excel(workbook, index=False, header=False)
    result = dbfileinput_tool(
        {},
        {
            "file": f"{workbook}|||`Sheet1$`",
            "file_attributes": {"FileFormat": "25"},
            "format_specific_options": {"FirstRowData": {"text": "True"}, "ImportLine": {"text": "1"}},
        },
        workflow_context,
    )

    output = result["Output"]
    assert output.columns.tolist() == ["F1", "F2", "F3", "F4"]
    assert output.iloc[0].to_dict() == {"F1": 2, "F2": 100, "F3": "Corporate", "F4": "No"}


def test_dbfileinput_excel_named_range_and_sheet_names(tmp_path, workflow_context):
    from openpyxl import Workbook
    from openpyxl.workbook.defined_name import DefinedName

    workbook = Workbook()
    workbook.active.title = "Sales"
    workbook.active.append(["ignored", "name", "Amount"])
    workbook.active.append(["ignored", "A", 10])
    workbook.active.append(["outside range", "B", 20])
    workbook.create_sheet("Archive")
    workbook.defined_names.add(DefinedName("CurrentSales", attr_text="'Sales'!$B$1:$C$2"))
    path = tmp_path / "sales.xlsx"
    workbook.save(path)

    for selector, expected in (
        ("`CurrentSales`", [{"name": "A", "Amount": 10}]),
        ("<List of Sheet Names>", [{"Sheet Names": "Sales"}, {"Sheet Names": "Archive"}]),
    ):
        result = dbfileinput_tool(
            {}, {"file": f"{path}|||{selector}", "file_attributes": {"FileFormat": "25"}},
            workflow_context,
        )
        assert result["Output"].to_dict("records") == expected


def test_dbfileinput_reads_yxdb_schema_and_null_values(workflow_context):
    output = dbfileinput_tool(
        {},
        {"file": "tests/fixtures/parity/native_textinput.yxdb", "file_attributes": {"RecordLimit": "2"}},
        workflow_context,
    )["Output"]
    assert output.to_dict("records") == [{"key": "a", "label": "中文"}, {"key": "b", "label": None}]
    assert output.attrs["alteryx_schema"][1] == {
        "name": "label", "type": "WString", "size": "3", "scale": None
    }


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
