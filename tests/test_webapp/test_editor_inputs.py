"""Editor import, preview and configuration round trips (no native parity claim)."""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "webapp"))
import server  # noqa: E402
from graph_compiler import compile_graph_to_yxmd  # noqa: E402
from backend import compile_workflow  # noqa: E402
from alteryx2python.parser.xml_parser import XmlWorkflowParser  # noqa: E402


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "WEBAPP_DIR", tmp_path)
    return tmp_path


def imported(name, content, **kwargs):
    return server._import_data({"name": name, "content": base64.b64encode(content).decode(), **kwargs})


def node(node_id, kind, config):
    return {"id": node_id, "type": kind, "x": 0, "y": 0, "config": config}


def edge(source, target, anchor="Output"):
    return {"from": source, "fromAnchor": anchor, "to": target, "toAnchor": "Input"}


def run_export(graph, tmp_path):
    compiled = compile_workflow(graph, tmp_path)
    assert compiled["phase2Status"] == "compiled", compiled["blockers"]
    source = compiled["python"]
    assert "checkpoints" not in source and "run_workflow_graph" not in source
    namespace = {"__file__": str(tmp_path / "native.py")}
    exec(source, namespace)
    return namespace["run_workflow"](input_dir=tmp_path, output_dir=tmp_path / "native")


def test_csv_import_preserves_quoted_newline_comma_bom_and_chinese(uploads):
    result = imported("data.csv", '\ufeffName,Note,Qty\r\n中文,"a,b\nsecond line",2\r\n'.encode())
    assert result["fields"] == ["Name", "Note", "Qty"]
    assert result["rows"] == [["中文", "a,b\nsecond line", "2"]]
    assert pd.read_csv(result["file"]).iloc[0]["Note"] == "a,b\nsecond line"


@pytest.mark.parametrize("name,content,expected", [
    ("data.tsv", b"A\tB\n1\t2\n", [["1", "2"]]),
    ("data.csv", "名称,数量\n测试,2\n".encode("gb18030"), [["测试", "2"]]),
    ("data.csv", "A,B\n1,2\n".encode("utf-16"), [["1", "2"]]),
    ("header.csv", b"A,B\n", []),
])
def test_import_formats_and_empty_data(uploads, name, content, expected):
    assert imported(name, content)["rows"] == expected


@pytest.mark.parametrize("content", [b"", b"A,A\n1,2", b"A,\n1,2", b"A,B\n1,2,3"])
def test_invalid_file_is_rejected_without_creating_uploads(uploads, content):
    with pytest.raises(ValueError):
        imported("bad.csv", content)
    assert not (uploads / ".uploads").exists()


def test_import_preview_limit_does_not_truncate_runtime_data(uploads):
    content = ("A\n" + "\n".join(str(i) for i in range(750))).encode()
    result = imported("large.csv", content)
    assert result["rowCount"] == 750
    assert len(result["rows"]) == 100
    graph = {"name": "import", "nodes": [node("42", "DbFileInput", result)], "edges": []}
    preview = server._run(graph)["previews"][0]
    assert preview["node"] == "42"
    assert preview["rowCount"] == 750
    assert len(preview["rows"]) == 500
    assert len(preview["csv"].splitlines()) == 751
    graph["nodes"].append(node("43", "DbFileOutput", {"file": "all-records.csv"}))
    graph["edges"] = [edge("42", "43")]
    directory = run_export(graph, uploads)
    assert pd.read_csv(directory / "all-records.csv")["A"].tolist() == list(range(750))


def test_excel_sheet_selection_and_execution(uploads):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame({"A": [1, 2]}).to_excel(writer, index=False, sheet_name="First")
        pd.DataFrame({"Name": ["中文"], "Qty": [3]}).to_excel(writer, index=False, sheet_name="Second")
    first = imported("book.xlsx", buffer.getvalue())
    assert first["sheets"] == ["First", "Second"]
    second = server._import_data({"sourceFile": first["sourceFile"], "name": first["name"], "sheet": "Second"})
    assert second["rows"] == [["中文", "3"]]
    assert second["sheet"] == "Second"
    assert first["file"] != second["file"]
    with pytest.raises(ValueError, match="unavailable"):
        server._import_data({"sourceFile": str(uploads / "outside.csv")})


def test_record_id_config_and_utf8_sink_match_generated_python(tmp_path):
    output = tmp_path / "output.csv"
    output.write_text("do not overwrite", encoding="utf-8")
    graph = {"name": "unicode", "nodes": [
        node("7", "TextInput", {"fields": ["Name"], "rows": [["中文"]]}),
        node("9", "RecordID", {"fieldName": "RowNumber"}),
        node("11", "DbFileOutput", {"file": str(output)}),
    ], "edges": [edge("7", "9"), edge("9", "11")]}
    result = server._run(graph)
    assert output.read_text(encoding="utf-8") == "do not overwrite"
    assert result["columns"] == ["RowNumber", "Name"]
    assert result["rows"] == [["1", "中文"]]
    directory = run_export(graph, tmp_path)
    assert output.read_text(encoding="utf-8") == "do not overwrite"
    actual = pd.read_csv(directory / output.name)
    assert actual.columns.tolist() == result["columns"]
    assert actual["Name"].tolist() == ["中文"]
    assert actual["RowNumber"].tolist() == [1]


@pytest.mark.parametrize("anchor,expected", [("True", [3]), ("False", [1, 2])])
def test_filter_branch_boolean_expression_runtime_and_export(tmp_path, anchor, expected):
    output = tmp_path / "branch.csv"
    graph = {"name": "branches", "nodes": [
        node("1", "TextInput", {"fields": ["A", "B"], "rows": [["1", "1"], ["2", "0"], ["3", "1"]]}),
        node("2", "Filter", {"expression": "[A] >= 2 AND [B] = 1"}),
        node("3", "DbFileOutput", {"file": str(output)}),
    ], "edges": [edge("1", "2"), edge("2", "3", anchor)]}
    result = server._run(graph)
    assert [int(row[0]) for row in result["rows"]] == expected
    directory = run_export(graph, tmp_path)
    assert pd.read_csv(directory / output.name)["A"].tolist() == expected
    assert {p["anchor"] for p in result["previews"] if p["node"] == "2"} == {"True", "False"}


def test_select_unknown_and_unique_duplicates_are_not_dropped(tmp_path):
    graph = {"name": "select", "nodes": [
        node("1", "TextInput", {"fields": ["A", "B", "C"], "rows": [["x", "1", "3"], ["x", "1", "4"], ["y", "2", "5"]]}),
        node("2", "Select", {"fields": [{"field": "B", "selected": "False"}], "includeUnknown": True}),
        node("3", "Unique", {"field": "A"}),
        node("4", "DbFileOutput", {"file": str(tmp_path / "unique.csv")}),
    ], "edges": [edge("1", "2"), edge("2", "3"), edge("3", "4", "Duplicates")]}
    result = server._run(graph)
    assert result["columns"] == ["A", "C"]
    directory = run_export(graph, tmp_path)
    actual = pd.read_csv(directory / "unique.csv", dtype=str)
    assert actual.values.tolist() == result["rows"] == [["x", "4"]]


def test_generated_text_column_names_are_escaped(tmp_path):
    graph = {"nodes": [node("1", "TextInput", {"fields": ['quote"column', 'back\\slash'], "rows": [["one", "two"]]})], "edges": []}
    graph["nodes"].append(node("2", "DbFileOutput", {"file": "escaped.csv"}))
    graph["edges"] = [edge("1", "2")]
    directory = run_export(graph, tmp_path)
    actual = pd.read_csv(directory / "escaped.csv", keep_default_na=False)
    assert actual.columns.tolist() == graph["nodes"][0]["config"]["fields"]
    assert actual.values.tolist() == [["one", "two"]]


def test_file_input_compiles_to_real_dbfileinput_node(uploads):
    data = imported("test.csv", b"A,B\n1,2\n")
    graph = {"nodes": [node("1", "DbFileInput", data)], "edges": []}
    path = uploads / "test.yxmd"
    path.write_text(compile_graph_to_yxmd(graph), encoding="utf-8")
    workflow = XmlWorkflowParser().parse(path)
    assert workflow.nodes[0].tool_type == "DbFileInput"


@pytest.mark.parametrize("issue", ["missing", "duplicate", "cycle", "anchor"])
def test_invalid_graph_fails_before_execution(issue):
    graph = {"nodes": [node("1", "TextInput", {"fields": ["A"], "rows": [["1"]]}), node("2", "Sort", {"order": [{"field": "A", "order": "Ascending"}]})], "edges": []}
    if issue == "duplicate":
        graph["nodes"].append(graph["nodes"][0])
    elif issue == "cycle":
        graph["nodes"][0]["type"] = "Sort"
        graph["edges"] = [edge("1", "2"), edge("2", "1")]
    elif issue == "anchor":
        graph["edges"] = [edge("1", "2", "Bad")]
    with pytest.raises(ValueError):
        server._compile(graph)


@pytest.mark.parametrize("kind,config,fields,data", [
    ("TextToColumns", {"field": "A", "delimiter": "|", "numFields": "2", "rootName": "Part"}, ["A"], [["x|y|z"], ["one"]]),
    ("Rank", {"field": "A", "order": "Descending"}, ["A"], [["2"], ["3"], ["2"]]),
    ("RunningTotal", {"field": "A"}, ["A"], [["1"], ["3"], ["2"]]),
    ("DateTime", {"inputField": "A", "outputField": "Date", "format": "yyyy-MM-dd"}, ["A"], [["2026-11-10"], ["2026-11-11"]]),
    ("RegEx", {"field": "A", "pattern": "(abc)", "outputField": "Parsed"}, ["A"], [["abc"], ["ABC"], ["none"]]),
    ("Sample", {"mode": "Last", "n": "2"}, ["A"], [["1"], ["2"], ["3"]]),
    ("Summarize", {"actions": [{"field": "A", "action": "GroupBy", "rename": "Group"}, {"field": "B", "action": "Sum", "rename": ""}]}, ["A", "B"], [["z", "1"], ["a", "2"], ["z", "3"]]),
    ("Summarize", {"actions": [{"field": "A", "action": "GroupBy", "rename": ""}]}, ["A"], [["z"], ["a"], ["z"]]),
    ("Summarize", {"actions": [{"field": "A", "action": "Sum", "rename": "Total"}]}, ["A"], [["1"], ["2"]]),
    ("CrossTab", {"groupBy": "A", "header": "B", "dataField": "C", "method": "First"}, ["A", "B", "C"], [["z", "B", "1"], ["a", "A", "2"], ["z", "A", "3"]]),
    ("MultiRowFormula", {"expression": "[A] - [Row-1:A]", "fieldName": "Delta"}, ["A"], [["2"], ["3"], ["5"]]),
    ("Formula", {"expressions": [{"field": "B", "type": "Double", "size": "", "expression": "[A] * 2"}, {"field": "C", "type": "Double", "size": "", "expression": "[B] + 1"}]}, ["A"], [["1"], ["2"]]),
])
def test_visible_tool_configuration_matches_runtime_and_export(tmp_path, kind, config, fields, data):
    graph = {"name": kind, "nodes": [
        node("1", "TextInput", {"fields": fields, "rows": data}),
        node("2", kind, config), node("3", "DbFileOutput", {"file": str(tmp_path / "result.csv")}),
    ], "edges": [edge("1", "2"), edge("2", "3")]}
    result = server._run(graph)
    directory = run_export(graph, tmp_path)
    actual = pd.read_csv(directory / "result.csv", dtype=str, keep_default_na=False)
    assert actual.columns.tolist() == result["columns"]
    assert actual.values.tolist() == result["rows"]


@pytest.mark.parametrize("anchor", ["Join", "Left", "Right"])
def test_join_ports_preserve_schema_and_use_correct_input_order(tmp_path, anchor):
    graph = {"name": "join", "nodes": [
        node("1", "TextInput", {"fields": ["Key", "A"], "rows": [["1", "a"], ["2", "b"]]}),
        node("2", "TextInput", {"fields": ["Key", "B"], "rows": [["2", "c"], ["3", "d"]]}),
        node("3", "Join", {"leftField": "Key", "rightField": "Key"}),
        node("4", "DbFileOutput", {"file": str(tmp_path / "join.csv")}),
    ], "edges": [
        {"from": "2", "fromAnchor": "Output", "to": "3", "toAnchor": "Right"},
        {"from": "1", "fromAnchor": "Output", "to": "3", "toAnchor": "Left"},
        edge("3", "4", anchor),
    ]}
    result = server._run(graph)
    directory = run_export(graph, tmp_path)
    actual = pd.read_csv(directory / "join.csv", dtype=str, keep_default_na=False)
    assert actual.columns.tolist() == result["columns"]
    assert actual.values.tolist() == result["rows"]

