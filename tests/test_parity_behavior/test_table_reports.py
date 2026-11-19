import base64
import gzip
import json
import re
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
import pytest

from alteryx2python.parity.behavior import compare_behavior_runs
from alteryx2python.parity.checkpoints import checkpoint_policy, coarse_rules, coarse_snapshot
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


def test_numeric_text_checkpoint_pairs_duplicates_and_embeds_both_original_values(tmp_path):
    columns = ["Trade ID", "Quantity", "Price", "Instrument Version"]
    designer = snapshot(columns, [[" 427732107009", "1.0", "6938.10", "2"]] * 2
                        + [[" 427732107009", "2.0", "6950.125", "3"]])
    designer["schema"] = [{"name": name, "type": "V_WString"} for name in columns]
    python = snapshot(columns, [[427732107009, 2, 6950.125, 3]] + [[427732107009, 1, 6938.1, 2]] * 2)

    def run(producer, frame):
        return {"producer": producer, "source_sha256": "source", "runtime_sha256": "runtime", "status": "success",
                "nodes": {"5": {"tool_type": "DynamicInput", "status": "success", "outputs": {"Output": frame}}}}

    left, right = run("alteryx", designer), run("python", python)
    result = compare_behavior_runs(left, right, "runtime", align_checkpoints=True,
                                   presentation_policy=(set(), {}))
    finding, = result["comparisons"]
    assert result["status"] == "coarse_match"
    assert finding["order_differences"] == ["rows"]
    assert finding["exact_comparison"]["status"] == "mismatch"
    write_table_reports(tmp_path, left, right, result, (None, None))
    rows_by_kind = {}
    for path in (tmp_path / "tables").glob("*.js"):
        if path.name != "view.js":
            data = re.search('= "([^"]+)";', path.read_text(encoding="ascii"))[1]
            rows = json.loads(gzip.decompress(base64.b64decode(data)))["rows"]
            rows_by_kind[rows[0][0][0]] = rows
    expected_id = rows_by_kind["string"][0][0]
    actual_id = rows_by_kind["int"][1][0]
    assert expected_id[:2] == ["string", " 427732107009"]
    assert actual_id[:2] == ["int", "427732107009"]
    assert expected_id[3] == actual_id[3]

    python["rows"][1] = python["rows"][0].copy()
    mismatched = compare_behavior_runs(left, right, "runtime", align_checkpoints=True,
                                       presentation_policy=(set(), {}))
    assert mismatched["status"] == "mismatch"


@pytest.mark.parametrize(("column", "expected", "actual", "match"), [
    ("Price", ["1.23000000000000000000000000000001"], [Decimal("1.23000000000000000000000000000002")], False),
    ("Price", ["1.000001"], [1.0], False),
    ("Price", ["1.20"], ["1.2"], False),
    ("Price", ["1.20"], [1.2], True),
    ("Amount", ["00123"], [123], False),
    ("Trade ID", [" 00123"], [123], False),
    ("Trade ID", [" 123", "123"], [123, 123], False),
    ("Trade ID", [" 123", " 123"], [123, 123], True),
    ("Trade ID", [" 9007199254740993"], [9007199254740993], True),
    ("Trade ID", [" 9007199254740993"], [9007199254740992.0], False),
    ("Instrument Version", ["1.0"], [1], False),
])
def test_numeric_text_rules_keep_meaningful_digits_and_identifier_variants(column, expected, actual, match):
    left = snapshot([column], [[value] for value in expected])
    right = snapshot([column], [[value] for value in actual])
    rules = coarse_rules(left, right, set())
    result = compare_snapshots(coarse_snapshot(left, rules), coarse_snapshot(right, rules))
    assert result["values_match"] is match
