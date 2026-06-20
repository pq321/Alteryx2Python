import pandas as pd
import pytest

from alteryx2python.tools.dbfileoutput import dbfileoutput_tool


def test_dbfileoutput_writes_csv_file(workflow_context, tmp_path):
    output_path = tmp_path / "out.csv"
    frame = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})

    result = dbfileoutput_tool(
        {"Input": frame},
        {"file": str(output_path), "file_attributes": {"FileFormat": "0"}},
        workflow_context,
    )

    assert result == {}
    assert output_path.read_text(encoding="utf-8").splitlines() == ["a,b", "1,x", "2,y"]
    assert workflow_context.traces[-1].outputs == {}


def test_dbfileoutput_defers_excel_output(workflow_context, tmp_path):
    with pytest.raises(NotImplementedError, match="Excel output"):
        dbfileoutput_tool(
            {"Input": pd.DataFrame({"a": [1]})},
            {"file": str(tmp_path / "out.xlsx"), "file_attributes": {"FileFormat": "25"}},
            workflow_context,
        )


def test_dbfileoutput_expands_alteryx_temp_token(workflow_context, tmp_path, monkeypatch):
    monkeypatch.setenv("TEMP", str(tmp_path))

    dbfileoutput_tool(
        {"Input": pd.DataFrame({"a": [1]})},
        {"file": "%temp%token-output.csv", "file_attributes": {"FileFormat": "0"}},
        workflow_context,
    )

    assert (tmp_path / "token-output.csv").read_text(encoding="utf-8").splitlines() == ["a", "1"]
