from pathlib import Path

from alteryx2python.tools.directory import directory_tool


def test_directory_lists_matching_files(tmp_path: Path, workflow_context):
    (tmp_path / "a.csv").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "c.csv").write_text("c", encoding="utf-8")

    output = directory_tool(
        {},
        {"directory": str(tmp_path), "file_spec": "*.csv", "include_subdirs": False},
        workflow_context,
    )["Output"]

    assert output["FileName"].tolist() == ["a.csv"]


def test_directory_can_include_subdirectories(tmp_path: Path, workflow_context):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "c.csv").write_text("c", encoding="utf-8")

    output = directory_tool(
        {},
        {"directory": str(tmp_path), "file_spec": "*.csv", "include_subdirs": True},
        workflow_context,
    )["Output"]

    assert output["FileName"].tolist() == ["c.csv"]
