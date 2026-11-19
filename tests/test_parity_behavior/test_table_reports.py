import base64
import gzip
import json
import re
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd

from alteryx2python.parity.behavior import compare_behavior_runs
from alteryx2python.parity.checkpoints import checkpoint_policy
from alteryx2python.parity.snapshot import compare_snapshots, frame_snapshot
from alteryx2python.parity.table_reports import write_table_reports


def snapshot(columns, rows):
    return frame_snapshot(pd.DataFrame(rows, columns=columns, dtype=object))


def test_native_field_type_label_does_not_change_behavioral_comparison():
    designer = snapshot(["Code"], [["00123"], [""]])
    designer["schema"] = [{"name": "Code", "type": "V_WString", "size": 64, "scale": None}]
    python = snapshot(["Code"], [["00123"], [""]])

    result = compare_snapshots(designer, python, align_columns=True, align_rows=True)
    assert result["status"] == "match"
    assert result["value_differences"] == []
    assert not result["schema_verified"]

    python["rows"][1][0] = {"kind": "null"}
    result = compare_snapshots(designer, python, align_columns=True, align_rows=True)
    assert result["status"] == "mismatch"
    assert result["value_differences"][0]["actual"] == {"kind": "null"}


def test_reordering_matches_with_duplicate_records_and_typed_values():
    designer = snapshot(["Product", "Count"], [["001", 2], ["001", 2], ["002", 1]])
    python = snapshot(["Count", "Product"], [[1.0, "002"], [2, "001"], [2.0, "001"]])

    comparison = compare_snapshots(designer, python, align_columns=True, align_rows=True)
    assert comparison["status"] == "match"
    assert comparison["order_differences"] == ["columns", "rows"]

    python["rows"][2] = python["rows"][0]
    assert compare_snapshots(designer, python, align_columns=True, align_rows=True)["status"] == "mismatch"


def test_display_alignment_keeps_explicit_sort_and_order_sensitive_inputs_strict():
    native, python = (
        {
            "producer": producer, "source_sha256": "workflow", "runtime_sha256": "runtime",
            "status": "success", "nodes": {
                str(index): {"tool_type": tool, "status": "success", direction: {anchor: frame}}
                for index, (tool, direction, anchor) in enumerate([
                    ("Join", "outputs", "Join"), ("Sort", "outputs", "Output"), ("Sample", "inputs", "Input"),
                ], 1)
            },
        }
        for producer, frame in (
            ("alteryx", snapshot(["Key"], [[1], [2]])), ("python", snapshot(["Key"], [[2], [1]])),
        )
    )
    native["input_sources"] = {"3": {"Input": {"node_id": "1", "anchor": "Join"}}}

    ordered = compare_behavior_runs(native, python, "runtime")
    assert [item["status"] for item in ordered["comparisons"]] == ["mismatch"] * 3
    aligned = compare_behavior_runs(native, python, "runtime", align_checkpoints=True)
    assert [item["status"] for item in aligned["comparisons"]] == ["match", "mismatch", "mismatch"]
    assert all(item["order_differences"] == ["rows"] for item in aligned["comparisons"])
    assert "duplicates_upstream" not in aligned["comparisons"][2]


def test_report_reuses_captured_table_and_preserves_html_as_cell_text(tmp_path):
    html = '<p>Notice</p><script>window.unwanted = true;</script>'
    frame = snapshot(["Email", "Note"], [[html, None], ["", ""]])
    run = {"nodes": {"7": {"tool_type": "Formula", "outputs": {"Output": frame}}}}
    comparison = {
        "node_id": "7", "direction": "outputs", "anchor": "Output", "status": "match",
    }
    parity = {"artifact_differences": [], "outcome_differences": [], "comparisons": [comparison]}
    write_table_reports(tmp_path, run, run, parity, ("7", None))

    report = (tmp_path / comparison["table_report"]).read_text(encoding="utf-8")
    assert html not in report
    data_file, = [path for path in (tmp_path / "tables").glob("*.js") if path.name != "view.js"]
    data = re.search('= "([^"]+)";', data_file.read_text(encoding="ascii"))[1]
    rows = json.loads(gzip.decompress(base64.b64decode(data)))["rows"]
    assert rows == [[["string", html], ["null", None]], [["string", ""], ["string", ""]]]


def test_presentation_coarse_match_keeps_typed_exact_values_and_protects_join_keys(tmp_path):
    columns = ["Account", "AsOf", "Price", "Note"]
    expected = snapshot(columns, [["0010", datetime(2026, 10, 13), Decimal("124.87"), None],
                                  ["0020", datetime(2026, 10, 13), Decimal("-12.35"), "ready"]])
    expected["schema"] = [{"name": column, "type": kind, "scale": scale} for column, kind, scale in
                          zip(columns, ["V_WString", "Date", "FixedDecimal", "V_WString"], [None, None, 2, None])]
    actual = snapshot(columns, [["0020", "2026-10-13", Decimal("-12.345"), "ready"],
                                ["0010", "2026-10-13", 124.87001, ""]])
    workflow = SimpleNamespace(nodes=[
        SimpleNamespace(node_id="37", config={"normalized": {"summarize_fields": [
            {"field": "AccountSrc", "rename": "Account", "action": "GroupBy"},
        ]}}),
        SimpleNamespace(node_id="41", config={"normalized": {"joins": [{"field": "Account"}]}}),
    ])
    policy = checkpoint_policy(workflow)

    def run(producer, frame):
        return {"producer": producer, "source_sha256": "source", "runtime_sha256": "runtime", "status": "success",
                "nodes": {"37": {"tool_type": "Summarize", "status": "success", "outputs": {"Output": frame}}}}

    native, python = run("alteryx", expected), run("python", actual)
    strict = compare_behavior_runs(native, python, "runtime", align_checkpoints=True)
    assert strict["status"] == "mismatch"
    comparison = compare_behavior_runs(native, python, "runtime", align_checkpoints=True, presentation_policy=policy)
    checkpoint, = comparison["comparisons"]
    assert comparison["status"] == checkpoint["status"] == "coarse_match"
    assert checkpoint["exact_comparison"]["status"] == "mismatch"
    assert checkpoint["alignment_keys"] == ("Account",)
    assert checkpoint["coarse_rules"] == {"AsOf": "date", "Price": 2, "Note": "empty"}
    assert checkpoint["order_differences"] == ["rows"]
    write_table_reports(tmp_path, native, python, comparison, (None, None))
    assert checkpoint["table_report"] == "tables/node37-anchor1.html"
    html = (tmp_path / checkpoint["table_report"]).read_text(encoding="utf-8")
    assert '"alignmentKeys":["Account"]' in html
    assert '"status":"coarse_match"' in html
    for column, left, right in (
        (0, {"kind": "null"}, {"kind": "string", "value": ""}),
        (1, expected["rows"][0][1], {"kind": "string", "value": "2026-10-13T00:00:01"}),
        (2, expected["rows"][0][2], {"kind": "decimal", "value": "124.88"}),
        (3, {"kind": "null"}, {"kind": "string", "value": "NULL"}),
    ):
        left_cell, right_cell = expected["rows"][0][column], actual["rows"][1][column]
        expected["rows"][0][column], actual["rows"][1][column] = left, right
        comparison = compare_behavior_runs(native, python, "runtime", align_checkpoints=True, presentation_policy=policy)
        assert comparison["status"] == "mismatch"
        expected["rows"][0][column], actual["rows"][1][column] = left_cell, right_cell


def test_null_checks_protect_source_field_through_a_select_rename():
    workflow = SimpleNamespace(nodes=[
        SimpleNamespace(node_id="15", config={"normalized": {"select_fields": [
            {"source": "Memo", "rename": "Display name", "selected": True},
        ]}}),
        SimpleNamespace(node_id="20", config={"normalized": {"expression": "NOT IsNull([Display name])"}}),
    ])
    protected, _ = checkpoint_policy(workflow)
    assert protected == {"memo", "display name"}
