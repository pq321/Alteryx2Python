"""Web editor backend: graph compilation and standalone codegen equivalence."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "webapp"))

from graph_compiler import compile_graph_to_yxmd  # noqa: E402
from standalone_gen import generate_standalone, translate_expression  # noqa: E402
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

    code, unsupported = generate_standalone(graph)
    assert unsupported == []
    script = tmp_path / "standalone.py"
    script.write_text(code, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    standalone_csv = tmp_path / "runtime.csv"  # the graph's configured output file
    assert standalone_csv.exists(), "standalone script did not write its output"
    standalone_frame = pd.read_csv(standalone_csv, dtype=object, keep_default_na=False)

    runtime_values = runtime_frame.astype(str).values.tolist()
    standalone_values = standalone_frame.astype(str).values.tolist()
    assert runtime_values == standalone_values
    assert list(standalone_frame.columns) == list(runtime_frame.columns)


def test_translate_expression_subset():
    assert translate_expression("[Qty] >= 4", "df") == 'df["Qty"] >= 4'
    assert translate_expression("[A] = 3 AND [B] = 4", "df") == 'df["A"] == 3 and df["B"] == 4'
    assert translate_expression("NOT [Flag]", "df") == 'not df["Flag"]'


def test_unsupported_tool_reports_instead_of_failing(tmp_path):
    graph = {
        "name": "unsupported",
        "nodes": [
            {"id": "1", "type": "TextInput", "x": 60, "y": 120, "config": {"fields": ["A"], "rows": [["1"]]}},
            {"id": "2", "type": "MysteryTool", "x": 260, "y": 120, "config": {}},
        ],
        "edges": [{"from": "1", "fromAnchor": "Output", "to": "2", "toAnchor": "Input"}],
    }
    code, unsupported = generate_standalone(graph)
    assert len(unsupported) == 1
    assert "MysteryTool" in unsupported[0]
    assert "MysteryTool" in code  # noted as a comment in the generated source
    with pytest.raises(ValueError):
        compile_graph_to_yxmd(graph)  # yxmd path is strict about known tools


def test_server_tool_palette_shape():
    from server import EDITOR_TOOLS

    types = {tool["type"] for tool in EDITOR_TOOLS}
    assert {"TextInput", "Filter", "Formula", "Summarize", "Join", "Union", "DbFileOutput"} <= types
    for tool in EDITOR_TOOLS:
        assert tool["label"] and tool["category"]
        assert isinstance(tool["inputs"], list) and isinstance(tool["outputs"], list)
        filter_tool = next(t for t in EDITOR_TOOLS if t["type"] == "Filter")
    assert filter_tool["outputs"] == ["True", "False"]
