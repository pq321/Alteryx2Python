"""Differential checks for standalone, statically configured IO bodies."""
import ast
import builtins
from copy import deepcopy
from pathlib import Path
import textwrap

import pandas as pd
import pytest

from alteryx2python.generator.native_io import lower_io
from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.dbfileinput import dbfileinput_tool
from alteryx2python.tools.dbfileoutput import dbfileoutput_tool
from alteryx2python.tools.textinput import textinput_tool


def _compile(kind, config, frame=None):
    original = deepcopy(config)
    lines = lower_io(kind, config, frame)
    assert lines is not None
    assert lower_io(kind, config, frame) == lines
    assert config == original
    source = "def run(source_frame=None, *, input_dir, output_dir):\n" + textwrap.indent("\n".join(lines), "    ")
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.Name) and node.id == "config" for node in ast.walk(tree))
    body = tree.body[0].body
    assert isinstance(body[-1], ast.Return)
    assert sum(isinstance(node, ast.Return) for node in ast.walk(tree)) == 1
    assert not any(isinstance(node, (ast.FunctionDef, ast.Lambda)) for statement in body for node in ast.walk(statement))

    def import_library(name, *args, **kwargs):
        assert not name.startswith(("alteryx2python", "alteryx_runtime"))
        return builtins.__import__(name, *args, **kwargs)

    namespace = {"pd": pd, "Path": Path, "__builtins__": {**vars(builtins), "__import__": import_library}}
    exec(compile(tree, "<native_io>", "exec"), namespace)
    return namespace["run"]


@pytest.mark.parametrize(
    "config",
    [
        {"fields": ["integer", "decimal", "mixed", "text"],
         "rows": [["1", "1.5", "2", "a"], ["-2", "2", "no", ""], ["3", "3.25", None, None]]},
        {"fields": ["integer", "decimal", "empty"],
         "rows": [["1", "1.5", ""], [None, None, None], ["", "", ""]]},
        {"fields": ["empty", "null"], "rows": [["", None], [None, ""]]},
        {"fields": ["integer", "text"], "rows": []},
        {"fields": ["special"], "rows": [["NaN"], ["inf"], ["-inf"], [None], [""]]},
        {"fields": ["literal", "number"], "rows": [["'\\\n", 2], ["plain", 4.5]]},
        {"fields": ["wide"], "rows": [[str(2**64)], ["-1"]]},
    ],
)
def test_text_input_matches_runtime(config, tmp_path):
    expected = textinput_tool({}, config, WorkflowContext())["Output"]
    actual = _compile("TextInput", config)(input_dir=tmp_path, output_dir=tmp_path)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)
    if config == {"fields": ["empty", "null"], "rows": [["", None], [None, ""]]}:
        assert actual.iloc[0, 0] == ""
        assert actual.iloc[0, 1] is None


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
@pytest.mark.parametrize(
    "header_options, has_header",
    [
        ({}, True),
        ({"HeaderRow": {"text": "True"}}, True),
        ({"HeaderRow": {"attributes": {"value": "False"}}}, False),
        ({"FirstRowData": {"text": "True"}}, False),
        ({"HeaderRow": "True", "FirstRowData": "True"}, True),
    ],
)
@pytest.mark.parametrize("limit", [None, "0", "2"])
def test_csv_headers_delimiters_offsets_and_limits(tmp_path, delimiter, header_options, has_header, limit):
    path = tmp_path / "records.csv"
    rows = ["ignored", "ignored"]
    if has_header:
        rows.append(delimiter.join(["name", "amount"]))
    rows += [delimiter.join(row) for row in [["alpha", "1"], ["beta", "2"], ["gamma", "3"]]]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    config = {
        "file": "records.csv|||ignored",
        "base_dir": str(tmp_path),
        "file_attributes": {"FileFormat": "0", "RecordLimit": limit},
        "format_specific_options": {
            **header_options, "Delimeter": {"text": delimiter}, "ImportLine": {"attributes": {"value": "3"}},
        },
    }
    expected = dbfileinput_tool({}, config, WorkflowContext())["Output"]
    actual = _compile("DbFileInput", config)(input_dir=tmp_path, output_dir=tmp_path)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


def test_csv_encoding_and_format_override(tmp_path):
    path = tmp_path / "records.dat"
    path.write_bytes("name;amount\ncaf\xe9;3\n".encode("latin-1"))
    config = {
        "file": str(path), "base_dir": str(tmp_path), "file_attributes": {"FileFormat": "0"},
        "format_specific_options": {"Delimeter": ";", "CodePage": {"text": "28591"}},
    }
    expected = dbfileinput_tool({}, config, WorkflowContext())["Output"]
    actual = _compile("DbFileInput", config)(input_dir=tmp_path, output_dir=tmp_path)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


@pytest.mark.parametrize("absolute", [False, True])
def test_input_binding_relocates_files_and_avoids_cwd_shadow(tmp_path, monkeypatch, absolute):
    original, relocated, cwd = [tmp_path / name for name in ("original", "relocated", "cwd")]
    for directory, amount in ((original, 3), (relocated, 9), (cwd, 15)):
        (directory / "data").mkdir(parents=True)
        (directory / "data" / "input.csv").write_text(f"amount\n{amount}\n", encoding="utf-8")
    config = {
        "file": str(original / "data" / "input.csv") if absolute else "data/input.csv",
        "base_dir": str(original),
    }
    run = _compile("DbFileInput", config)
    monkeypatch.chdir(cwd)
    expected = dbfileinput_tool({}, {"file": str(relocated / "data" / "input.csv")}, WorkflowContext())["Output"]
    actual = run(input_dir=relocated, output_dir=tmp_path)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


@pytest.mark.parametrize("selector", [None, "", "Data$", "`Data$`", " `Data$` "])
@pytest.mark.parametrize("header", [False, True])
def test_excel_sheet_headers_offsets_and_limits(tmp_path, selector, header):
    path = tmp_path / "input.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([["skip", "skip"], ["name", "amount"], ["alpha", 2], ["beta", 3], ["gamma", 4]]).to_excel(
            writer, sheet_name="Data", index=False, header=False,
        )
        pd.DataFrame({"other": [8]}).to_excel(writer, sheet_name="Other", index=False)
    config = {
        "file": "input.xlsx" + ("|||" + selector if selector is not None else ""),
        "base_dir": str(tmp_path), "file_attributes": {"FileFormat": "25", "RecordLimit": "2"},
        "format_specific_options": {"FirstRowData": {"text": str(not header)}, "ImportLine": {"text": "2"}},
    }
    expected = dbfileinput_tool({}, config, WorkflowContext())["Output"]
    actual = _compile("DbFileInput", config)(input_dir=tmp_path, output_dir=tmp_path)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


def test_excel_selects_nonfirst_sheet(tmp_path):
    path = tmp_path / "input.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"unused": [1]}).to_excel(writer, sheet_name="First", index=False)
        pd.DataFrame({"selected": [7]}).to_excel(writer, sheet_name="Target Sheet", index=False)
    config = {"file": str(path) + "|||`Target Sheet$`", "base_dir": str(tmp_path)}
    expected = dbfileinput_tool({}, config, WorkflowContext())["Output"]
    actual = _compile("DbFileInput", config)(input_dir=tmp_path, output_dir=tmp_path)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


def test_excel_missing_engine_retains_runtime_blocker(tmp_path, monkeypatch):
    def missing_engine(*args, **kwargs):
        raise ImportError("missing optional engine")

    config = {"file": "input.xlsx", "base_dir": str(tmp_path)}
    run = _compile("DbFileInput", config)
    monkeypatch.setattr(pd, "read_excel", missing_engine)
    with pytest.raises(NotImplementedError, match="optional Excel engine"):
        run(input_dir=tmp_path, output_dir=tmp_path)


@pytest.mark.parametrize("header", ["True", "False"])
@pytest.mark.parametrize("code_page", ["28591", "65001", "1200", "1252"])
@pytest.mark.parametrize("ending", ["LF", "CRLF"])
@pytest.mark.parametrize("limit", [None, "0", "2", "-1"])
def test_csv_output_matches_runtime_bytes(tmp_path, header, code_page, ending, limit):
    frame = pd.DataFrame({"name": ["caf\xe9", "a;\"b", None], "amount": [2.0, 1.25, None]})
    original = frame.copy(deep=True)
    expected_path = tmp_path / "expected.csv"
    config = {
        "file": str(expected_path), "file_attributes": {"FileFormat": "0", "MaxRecords": limit},
        "format_specific_options": {
            "HeaderRow": {"text": header}, "Delimeter": {"text": ";"},
            "CodePage": {"text": code_page}, "LineEndStyle": {"text": ending},
        },
    }
    dbfileoutput_tool({"Input": frame}, config, WorkflowContext())
    output_dir = tmp_path / "relocated" / "nested"
    result = _compile("DbFileOutput", config, "source_frame")(
        frame, input_dir=tmp_path, output_dir=output_dir,
    )
    assert result is None
    assert (output_dir / expected_path.name).read_bytes() == expected_path.read_bytes()
    pd.testing.assert_frame_equal(frame, original, check_exact=True)


@pytest.mark.parametrize("empty", [False, True])
def test_headerless_single_column_output_matches_runtime(tmp_path, empty):
    frame = pd.DataFrame({"value": pd.Series([] if empty else ["a,b", "one\ntwo", 3.0, None, ""], dtype=object)})
    expected_path = tmp_path / "plain.eml"
    config = {
        "file": str(expected_path) + "|||ignored", "format_specific_options": {"HeaderRow": "False"},
    }
    dbfileoutput_tool({"Input": frame}, config, WorkflowContext())
    output_dir = tmp_path / "output"
    _compile("DbFileOutput", config, "source_frame")(frame, input_dir=tmp_path, output_dir=output_dir)
    assert (output_dir / expected_path.name).read_bytes() == expected_path.read_bytes()


@pytest.mark.parametrize("header", ["True", "False"])
@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"value": pd.Series([1.2, None, 3.0], dtype="float32")}),
        pd.DataFrame({"value": pd.Series([1.2, None, 3.0], dtype="Float32")}),
        pd.DataFrame({"value": pd.Series([1.2, None, 3.0], dtype="Float64")}),
        pd.DataFrame({"value": pd.Series([1, None, 3], dtype="Int64")}),
        pd.DataFrame({"value": pd.Series(["a,b", None, ""], dtype="string")}),
        pd.DataFrame({"value": pd.Series(["a,b", None, ""], dtype="category")}),
        pd.DataFrame({"value": pd.to_datetime(["2024-01-01", None])}),
        pd.DataFrame({"value": pd.to_timedelta(["1 day", None])}),
        pd.DataFrame([[1.0, None], [2.5, "quoted,cell"]], columns=["same", "same"]),
        pd.DataFrame({"value": [1e15, 1e14, -3.0]}, index=[3, 3, 8]),
    ],
)
def test_output_scalar_formatting_matches_runtime(tmp_path, frame, header):
    config = {
        "file": str(tmp_path / "expected.csv"),
        "format_specific_options": {"HeaderRow": {"text": header}},
    }
    original = frame.copy(deep=True)
    dbfileoutput_tool({"Input": frame}, config, WorkflowContext())
    output_dir = tmp_path / "output"
    _compile("DbFileOutput", config, "source_frame")(frame, input_dir=tmp_path, output_dir=output_dir)
    assert (output_dir / "expected.csv").read_bytes() == (tmp_path / "expected.csv").read_bytes()
    pd.testing.assert_frame_equal(frame, original, check_exact=True)


@pytest.mark.parametrize(
    "kind, file, attributes, message",
    [
        ("DbFileInput", "input.yxdb", {"FileFormat": "0"}, "YXDB"),
        ("DbFileInput", "input.csv", {"FileFormat": "19"}, "YXDB"),
        ("DbFileInput", "input.json", {}, "Unsupported DbFileInput"),
        ("DbFileInput", "input.xlsx|||`NamedRange`", {}, "Named ranges"),
        ("DbFileInput", "input.xlsx|||<List of Sheet Names>", {}, "sheet-name list"),
        ("DbFileOutput", "output.xlsx", {}, "Excel output"),
        ("DbFileOutput", "output.dat", {"FileFormat": "25"}, "Excel output"),
        ("DbFileOutput", "output.yxdb", {"FileFormat": "19"}, "Unsupported DbFileOutput"),
    ],
)
def test_unsupported_formats_block_at_compile_time(kind, file, attributes, message):
    with pytest.raises(UnsupportedLowering, match=message):
        lower_io(kind, {"file": file, "file_attributes": attributes}, "source_frame" if kind == "DbFileOutput" else None)


@pytest.mark.parametrize(
    "kind, config, frame",
    [
        ("TextInput", {"fields": [], "rows": []}, None),
        ("TextInput", {"fields": ["x", "x"], "rows": [["1", "2"]]}, None),
        ("TextInput", {"fields": ["x"], "rows": "dynamic"}, None),
        ("TextInput", {"fields": ["x", "y"], "rows": [["1"]]}, None),
        ("TextInput", {"fields": ["x"], "rows": ["invalid"]}, None),
        ("DbFileInput", {"file": "input.csv", "file_attributes": {"RecordLimit": "invalid"}}, None),
        ("DbFileInput", {"file": "input.csv", "format_specific_options": {"ImportLine": "invalid"}}, None),
        ("DbFileOutput", {"file": "output.csv", "file_attributes": {"MaxRecords": "invalid"}}, "source_frame"),
        ("DbFileInput", {}, None),
        ("DbFileOutput", {}, "source_frame"),
        ("DbFileOutput", {"file": "output.csv"}, None),
        ("DbFileInput", {"file": "input.csv"}, "source_frame"),
        ("TextInput", {"fields": ["x"], "rows": []}, "source_frame"),
    ],
)
def test_invalid_static_config_is_an_explicit_blocker(kind, config, frame):
    with pytest.raises(UnsupportedLowering):
        lower_io(kind, config, frame)


def test_unbound_absolute_input_is_blocked(tmp_path):
    with pytest.raises(UnsupportedLowering, match="portable binding"):
        lower_io("DbFileInput", {"file": str(tmp_path / "outside.csv"), "base_dir": str(tmp_path / "base")}, None)


def test_windows_paths_are_portable():
    lines = lower_io("DbFileInput", {"file": "C:\\workflow\\data\\input.csv", "base_dir": "C:\\workflow"}, None)
    assert lines[0] == "path = input_dir / 'data/input.csv'"
    lines = lower_io("DbFileOutput", {"file": "C:\\workflow\\results\\output.csv"}, "source_frame")
    assert "path = output_dir / 'output.csv'" in lines


def test_other_tools_are_not_claimed():
    assert lower_io("Filter", {}, "source_frame") is None
