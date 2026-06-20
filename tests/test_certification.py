import pytest
import subprocess
import sys

from alteryx2python.certification import assert_nodes_certifiable, certification_issues_for_nodes
from alteryx2python.ir.models import NodeIR, WorkflowIR


def _workflow(tool_type: str = "Select", config: dict | None = None) -> WorkflowIR:
    normalized_config = config if config is not None else {"select_fields": [{"source": "a"}]}
    return WorkflowIR(
        workflow_id="cert-test",
        workflow_name="cert-test",
        source_file="synthetic",
        source_hash="hash",
        parser_version="0.1.0",
        migration_spec_version="0.1.0",
        nodes=[
            NodeIR(
                node_id="1",
                source_tool_id="1",
                tool_type=tool_type,
                tool_name=tool_type,
                config={"normalized": normalized_config},
            )
        ],
        edges=[],
    )


def test_certification_precheck_allows_certifiable_tools():
    assert certification_issues_for_nodes(_workflow("Select"), ["1"]) == []


def test_certification_precheck_reports_uncertifiable_tools():
    assert certification_issues_for_nodes(_workflow("Formula"), ["1"]) == [
        "Node 1 tool Formula is not marked certifiable"
    ]


@pytest.mark.parametrize(
    ("tool_type", "config", "expected"),
    [
        (
            "DbFileInput",
            {
                "file": "input.yxdb",
                "file_attributes": {"FileFormat": "19"},
            },
            "YXDB input is deferred",
        ),
        (
            "DbFileOutput",
            {
                "file": "output.xlsx",
                "file_attributes": {"FileFormat": "25"},
            },
            "Excel output is deferred",
        ),
        (
            "Join",
            {"join_by_record_pos": True, "joins": []},
            "join-by-record-position is deferred",
        ),
        (
            "Sort",
            {"sort_fields": [{"field": "CustomerID", "order": "Sideways"}]},
            "order Sideways is not observed",
        ),
        (
            "Select",
            {"select_fields": [{}]},
            "select field requires source",
        ),
        (
            "Select",
            {"select_fields": ["bad"]},
            "malformed select field",
        ),
        (
            "Sort",
            {"sort_fields": [{}]},
            "sort field requires field",
        ),
        (
            "Sort",
            {"sort_fields": ["bad"]},
            "malformed sort field",
        ),
        (
            "TextInput",
            {"fields": ["a"], "rows": [["x", "y"]]},
            "row width does not match fields",
        ),
        (
            "TextInput",
            {"fields": ["a"], "rows": [["x"]], "num_rows": 2},
            "num_rows does not match rows",
        ),
        (
            "TextInput",
            {"fields": "a", "rows": [["x"]]},
            "expected observed fields and rows",
        ),
        (
            "TextInput",
            {"fields": ["a"], "rows": "x"},
            "expected observed fields and rows",
        ),
        (
            "TextInput",
            {"fields": [], "rows": []},
            "fields are required",
        ),
        (
            "TextInput",
            {"fields": ["a"], "rows": ["x"]},
            "row entries must be lists",
        ),
    ],
)
def test_certification_precheck_rejects_deferred_configs_for_certifiable_tools(tool_type, config, expected):
    issues = certification_issues_for_nodes(_workflow(tool_type, config), ["1"])

    assert len(issues) == 1
    assert expected in issues[0]


def test_certification_precheck_raises_for_uncertifiable_path():
    with pytest.raises(AssertionError, match="Formula is not marked certifiable"):
        assert_nodes_certifiable(_workflow("Formula"), ["1"])


def test_certification_module_imports_cleanly():
    import alteryx2python.certification as certification

    assert certification.assert_nodes_certifiable is assert_nodes_certifiable


def test_certification_module_imports_in_clean_interpreter():
    result = subprocess.run(
        [sys.executable, "-c", "import alteryx2python.certification; print('ok')"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
