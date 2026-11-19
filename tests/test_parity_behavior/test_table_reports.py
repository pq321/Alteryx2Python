import base64
import gzip
import json
import re

import pandas as pd

from alteryx2python.parity.behavior import compare_behavior_runs
from alteryx2python.parity.snapshot import compare_snapshots, frame_snapshot
from alteryx2python.parity.table_reports import write_table_reports


def snapshot(columns, rows):
    return frame_snapshot(pd.DataFrame(rows, columns=columns, dtype=object))


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
