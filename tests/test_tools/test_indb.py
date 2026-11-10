import sqlite3
import pandas as pd
import pytest

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.indb import ANCHORS, IMPLEMENTATIONS, TOOL_CLASSES


def test_catalog_and_anchor_contract():
    assert len(IMPLEMENTATIONS) == 17
    assert "LockInTranspose" in IMPLEMENTATIONS
    assert ANCHORS["LockInJoin"] == (("Left", "Right"), ("Join", "Left", "Right"))


def test_filter_and_union_execute_with_original_trace():
    ctx = WorkflowContext()
    filt = TOOL_CLASSES["LockInFilter"]()
    out = filt.execute({"Input": pd.DataFrame({"x": [1, 2, 3]})}, {"expression": "[x] > 1"}, ctx)
    assert out["True"]["x"].tolist() == [2, 3]
    assert ctx.traces[-1].tool_type == "LockInFilter"
    union = TOOL_CLASSES["LockInUnion"]()
    out = union.execute({"Input": out["True"], "Input_2": pd.DataFrame({"x": [4]})}, {"mode": "ByName"}, ctx)
    assert out["Output"]["x"].tolist() == [2, 3, 4]


def test_sqlite_input_output_are_real_and_validate_prerequisites(tmp_path):
    db = str(tmp_path / "fixture.sqlite")
    with sqlite3.connect(db) as conn:
        pd.DataFrame({"id": [1, 2], "v": ["a", "b"]}).to_sql("source", conn, index=False)
    ctx = WorkflowContext()
    reader = TOOL_CLASSES["LockInInput"]()
    result = reader.execute({}, {"database": db, "table": "source"}, ctx)
    assert result["Output"].to_dict("records") == [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
    writer = TOOL_CLASSES["LockInOutput"]()
    writer.execute({"Input": result["Output"]}, {"database": db, "table": "sink"}, ctx)
    with sqlite3.connect(db) as conn:
        assert pd.read_sql_query("select * from sink", conn).shape == (2, 2)
    with pytest.raises(ValueError): reader.execute({}, {"connection": "postgres://server/db"}, ctx)


def test_sqlite_table_names_are_quoted_and_sql_filter_is_explicit():
    import tempfile
    db = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name
    with sqlite3.connect(db) as conn:
        pd.DataFrame({"x": [1, 2]}).to_sql("a table", conn, index=False)
    ctx = WorkflowContext()
    result = IMPLEMENTATIONS["LockInInput"]({}, {"database": db, "table": "a table"}, ctx)
    assert result["Output"]["x"].tolist() == [1, 2]
    filtered = IMPLEMENTATIONS["LockInFilter"]({"Input": result["Output"]}, {"sql_expression": "x > 1"}, ctx)
    assert filtered["True"]["x"].tolist() == [2]
    with pytest.raises(Exception):
        IMPLEMENTATIONS["LockInInput"]({}, {"database": db, "table": "a table; DROP TABLE x"}, ctx)
