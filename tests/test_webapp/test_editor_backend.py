"""Web editor backend: graph compilation and standalone codegen equivalence."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "webapp"))

from graph_compiler import compile_graph_to_yxmd  # noqa: E402
from backend import compile_workflow  # noqa: E402
from workflow_documents import import_workflow  # noqa: E402
from alteryx2python.parser.xml_parser import XmlWorkflowParser  # noqa: E402
from alteryx2python.equivalence import find_output_node, run_python_workflow  # noqa: E402


def _demo_graph(output_file: str) -> dict:
    return {
        "name": "editor_test",
        "nodes": [
            {"id": "1", "type": "TextInput", "x": 60, "y": 120, "config": {
                "fields": ["Region", "Product", "Qty", "Price"],
                "rows": [
                    ["North", "Widget", "4", "2.5"],
                    ["South", "Gadget", "9", "1.5"],
                    ["North", "Gear", "2", "7.0"],
                    ["South", "Widget", "6", "3.0"],
                ],
            }},
            {"id": "2", "type": "Formula", "x": 260, "y": 120, "config": {
                "expressions": [{"field": "Total", "type": "Double", "size": "", "expression": "[Qty] * [Price]"}],
            }},
            {"id": "3", "type": "Filter", "x": 460, "y": 120, "config": {"expression": "[Qty] >= 4"}},
            {"id": "4", "type": "Sort", "x": 660, "y": 120, "config": {
                "order": [{"field": "Total", "order": "Descending"}],
            }},
            {"id": "5", "type": "DbFileOutput", "x": 860, "y": 120, "config": {"file": output_file}},
        ],
        "edges": [
            {"from": "1", "fromAnchor": "Output", "to": "2", "toAnchor": "Input"},
            {"from": "2", "fromAnchor": "Output", "to": "3", "toAnchor": "Input"},
            {"from": "3", "fromAnchor": "True", "to": "4", "toAnchor": "Input"},
            {"from": "4", "fromAnchor": "Output", "to": "5", "toAnchor": "Input"},
        ],
    }


def test_compiled_yxmd_parses_with_expected_tool_types(tmp_path):
    graph = _demo_graph(str(tmp_path / "out.csv"))
    yxmd = compile_graph_to_yxmd(graph)
    yxmd_path = tmp_path / "editor.yxmd"
    yxmd_path.write_text(yxmd, encoding="utf-8")
    workflow = XmlWorkflowParser().parse(yxmd_path)
    types = {node.tool_type for node in workflow.nodes}
    assert types == {"TextInput", "Formula", "Filter", "Sort", "DbFileOutput"}
    assert len(workflow.edges) == 4


def test_standalone_output_matches_runtime_output(tmp_path):
    """The compiled standalone pandas script and the canonical runtime must
    produce identical data for the same editor graph."""
    graph = _demo_graph(str(tmp_path / "runtime.csv"))
    yxmd = compile_graph_to_yxmd(graph)
    yxmd_path = tmp_path / "editor.yxmd"
    yxmd_path.write_text(yxmd, encoding="utf-8")

    runtime_frame = run_python_workflow(yxmd_path, find_output_node(yxmd_path), tmp_path / "runtime_out.csv")

    compiled = compile_workflow(graph, tmp_path)
    assert compiled["phase2Status"] == "compiled", compiled["blockers"]
    code = compiled["python"]
    assert "checkpoints" not in code and "run_workflow_graph" not in code
    script = tmp_path / "standalone.py"
    script.write_text(code, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(script), "--output-dir", str(tmp_path / "native")], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    standalone_csv = tmp_path / "native/runtime.csv"
    assert standalone_csv.exists(), "standalone script did not write its output"
    standalone_frame = pd.read_csv(standalone_csv, dtype=object, keep_default_na=False)

    runtime_values = runtime_frame.astype(str).values.tolist()
    standalone_values = standalone_frame.astype(str).values.tolist()
    assert runtime_values == standalone_values
    assert list(standalone_frame.columns) == list(runtime_frame.columns)


@pytest.mark.parametrize("expression,expected", [
    ("[Qty] >= 4", [5, 6]),
    ("[A] = 3 AND [B] = 4", [3]),
    ("![Flag]", [3, 6]),
])
def test_canonical_expression_export_matches_runtime(tmp_path, expression, expected):
    from server import _run
    graph = _demo_graph("expression.csv")
    graph["nodes"][0]["config"] = {"fields": ["Qty", "A", "B", "Flag"],
                                     "rows": [["3", "3", "4", "0"], ["5", "3", "0", "1"], ["6", "0", "4", "0"]]}
    graph["nodes"] = [graph["nodes"][0], graph["nodes"][2], graph["nodes"][4]]
    graph["nodes"][1]["config"]["expression"] = expression
    graph["edges"] = [{"from": "1", "to": "3"}, {"from": "3", "fromAnchor": "True", "to": "5"}]
    result = _run(graph)
    assert result["phase2Status"] == "compiled", result["blockers"]
    namespace = {"__file__": str(tmp_path / "expression.py")}
    exec(result["python"], namespace)
    namespace["run_workflow"](input_dir=tmp_path, output_dir=tmp_path)
    assert pd.read_csv(tmp_path / "expression.csv")["Qty"].tolist() == expected
    assert [int(row[0]) for row in result["rows"]] == expected


def test_unimplemented_expression_syntax_blocks_without_regex_rewriting(tmp_path):
    from backend import ApiError
    from server import _run
    graph = {"nodes": [
        {"id": "1", "type": "TextInput", "config": {"fields": ["Flag"], "rows": [["0"], ["1"]]}},
        {"id": "2", "type": "Filter", "config": {"expression": "NOT [Flag]"}},
    ], "edges": [{"from": "1", "to": "2"}]}
    result = compile_workflow(graph, tmp_path)
    assert result["phase2Status"] == "blocked" and result["python"] == ""
    assert result["blockers"][0]["errorType"] == "UnsupportedExpressionError"
    with pytest.raises(ApiError) as raised:
        _run(graph)
    assert raised.value.status == 422 and raised.value.code == "runtime_unavailable"


def test_unsupported_tool_reports_instead_of_failing(tmp_path):
    graph = {
        "name": "unsupported",
        "nodes": [
            {"id": "1", "type": "TextInput", "x": 60, "y": 120, "config": {"fields": ["A"], "rows": [["1"]]}},
            {"id": "2", "type": "MysteryTool", "x": 260, "y": 120, "config": {}},
        ],
        "edges": [{"from": "1", "fromAnchor": "Output", "to": "2", "toAnchor": "Input"}],
    }
    with pytest.raises(ValueError):
        compile_graph_to_yxmd(graph)  # yxmd path is strict about known tools
    imported = import_workflow({"name": "unknown.yxmd", "xml":
        '<AlteryxDocument><Nodes><Node ToolID="1"><GuiSettings Plugin="Vendor.MysteryTool"/>'
        '<Properties><Configuration/></Properties></Node></Nodes></AlteryxDocument>'}, tmp_path)
    result = compile_workflow(imported, tmp_path)
    assert result["phase2Status"] == "blocked" and result["python"] == ""
    assert result["unsupported"] and result["blockers"][0]["code"] == "phase2_unsupported"


def test_server_tool_palette_shape():
    from server import EDITOR_TOOLS

    types = {tool["type"] for tool in EDITOR_TOOLS}
    assert {"TextInput", "Filter", "Formula", "Summarize", "Join", "Union", "DbFileOutput"} <= types
    for tool in EDITOR_TOOLS:
        assert tool["label"] and tool["category"]
        assert isinstance(tool["inputs"], list) and isinstance(tool["outputs"], list)
        filter_tool = next(t for t in EDITOR_TOOLS if t["type"] == "Filter")
    assert filter_tool["outputs"] == ["True", "False"]
