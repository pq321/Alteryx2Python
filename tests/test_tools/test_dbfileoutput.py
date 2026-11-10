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


def test_dbfileoutput_honors_utf8_code_page_without_losing_unicode(workflow_context, tmp_path):
    output = tmp_path / "unicode.csv"
    dbfileoutput_tool({"Input": pd.DataFrame({"文字": ["中文", "🙂"]})},
                      {"file": str(output), "file_attributes": {"FileFormat": "0"},
                       "format_specific_options": {"CodePage": {"text": "65001"}}}, workflow_context)
    assert pd.read_csv(output, encoding="utf-8")["文字"].tolist() == ["中文", "🙂"]


def test_dbfileoutput_writes_single_column_text_without_header(workflow_context, tmp_path):
    output_path = tmp_path / "DraftEmail.eml"
    frame = pd.DataFrame({"Field1": ["MIME-Version: 1.0", "<tr><td>x</td></tr>"]})

    dbfileoutput_tool(
        {"Input": frame},
        {
            "file": str(output_path),
            "file_attributes": {"FileFormat": "0"},
            "format_specific_options": {"HeaderRow": {"text": "False"}, "LineEndStyle": {"text": "CRLF"}},
        },
        workflow_context,
    )

    assert output_path.read_bytes() == b"MIME-Version: 1.0\r\n<tr><td>x</td></tr>\r\n"


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
