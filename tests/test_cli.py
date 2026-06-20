import json
import subprocess
import sys
from pathlib import Path


COMBINE_WORKFLOW = "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd"
COMBINE_EXPECTED = "tests/fixtures/real_workflows/combine_customer_profile_expected.csv"
TEXT_INPUT_WORKFLOW = "D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/01 In Out/Text_Input.yxmd"
NORMALIZE_STRING_WORKFLOW = "D:/Alteryx/Samples/en/04 Basic/01 Normalize_a_string_field.yxmd"


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "alteryx2python.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _run_console_script(*args):
    return subprocess.run(
        ["uv", "run", "alteryx2python", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _json(stdout: str):
    return json.loads(stdout)


def test_cli_inspect_reports_workflow_tools_and_dependencies(tmp_path):
    log_path = tmp_path / "inspect.json"

    result = _run_cli("inspect", COMBINE_WORKFLOW, "--log", str(log_path))

    assert result.returncode == 0, result.stderr
    report = _json(result.stdout)
    assert report["status"] == "ok"
    assert report["workflow"]["node_count"] == 12
    assert "DbFileInput" in report["tool_types"]
    assert "Sort" in report["tool_types"]
    assert "Excel.CustomerLocationData.xlsx|||`Customers$`" in ";".join(report["external_dependencies"])
    assert json.loads(log_path.read_text(encoding="utf-8")) == report


def test_cli_compact_reports_topology_preserving_view(tmp_path):
    log_path = tmp_path / "compact.json"

    result = _run_cli("compact", COMBINE_WORKFLOW, "--log", str(log_path))

    assert result.returncode == 0, result.stderr
    report = _json(result.stdout)
    compact = report["compact_workflow"]
    assert report["status"] == "ok"
    assert compact["workflow"]["node_count"] == 12
    assert compact["workflow"]["edge_count"] == 6
    assert len(compact["nodes"]) == 12
    assert len(compact["edges"]) == 6
    assert {"id", "type", "inputs", "outputs", "incoming", "outgoing", "config_summary"} <= set(
        compact["nodes"][0]
    )
    assert all("from_node" in edge and "to_node" in edge for edge in compact["edges"])
    assert "raw_gui_settings" not in result.stdout
    assert json.loads(log_path.read_text(encoding="utf-8")) == report


def test_cli_inspect_compact_uses_compact_report_shape():
    result = _run_cli("inspect", COMBINE_WORKFLOW, "--compact")

    assert result.returncode == 0, result.stderr
    report = _json(result.stdout)
    assert report["command"] == "compact"
    assert "compact_workflow" in report
    assert "nodes" not in report


def test_console_script_entrypoint_is_wired():
    result = _run_console_script("inspect", TEXT_INPUT_WORKFLOW)

    assert result.returncode == 0, result.stderr
    report = _json(result.stdout)
    assert report["status"] == "ok"
    assert report["workflow"]["workflow_name"] == "Text_Input"


def test_cli_certify_basic_workflow_matches_alteryx_oracle_byte_for_byte(tmp_path):
    output_path = tmp_path / "Excel.CustomerProfileOutput.csv"
    log_path = tmp_path / "certify.json"

    result = _run_cli(
        "certify",
        COMBINE_WORKFLOW,
        "--target-node",
        "23",
        "--override-output",
        f"23={output_path}",
        "--expect",
        COMBINE_EXPECTED,
        "--compare",
        "bytes",
        "--log",
        str(log_path),
    )

    assert result.returncode == 0, result.stderr
    report = _json(result.stdout)
    assert report["status"] == "certified"
    assert report["execution_order"] == ["1", "2", "7", "3", "4", "6", "23"]
    assert report["certification_issues"] == []
    assert report["compare"]["matches"] is True
    assert report["contract_evidence"]["7"]["passed"] is True
    assert report["contract_evidence"]["7"]["assertions"]
    assert report["runtime_result"]["contract_evidence"]["23"]["passed"] is True
    assert output_path.read_bytes() == Path(COMBINE_EXPECTED).read_bytes()
    assert json.loads(log_path.read_text(encoding="utf-8")) == report


def test_cli_compare_returns_nonzero_for_byte_mismatch(tmp_path):
    actual = tmp_path / "actual.csv"
    expected = tmp_path / "expected.csv"
    actual.write_text("a\n1\n", encoding="utf-8")
    expected.write_text("a\n2\n", encoding="utf-8")

    result = _run_cli("compare", "--actual", str(actual), "--expected", str(expected), "--mode", "bytes")

    assert result.returncode == 1
    report = _json(result.stdout)
    assert report["status"] == "mismatch"
    assert report["first_difference"]["index"] is not None


def test_cli_run_records_unimplemented_behavior_as_structured_error(tmp_path):
    log_path = tmp_path / "unsupported.json"

    result = _run_cli(
        "run",
        NORMALIZE_STRING_WORKFLOW,
        "--target-node",
        "97",
        "--log",
        str(log_path),
    )

    assert result.returncode == 2
    report = _json(result.stdout)
    assert report["status"] == "error"
    assert report["error"]["type"] == "NotImplementedError"
    assert "Unsupported workflow tool: RegEx" in report["error"]["message"]
    assert report["workflow"]["source_file"].endswith("01 Normalize_a_string_field.yxmd")
    assert report["target_node"] == "97"
    assert report["output_overrides"] == {}
    assert report["context_errors"] == ["Unsupported workflow tool: RegEx (node 97)"]
    assert report["trace"]["errors"] == ["Unsupported workflow tool: RegEx (node 97)"]
    assert json.loads(log_path.read_text(encoding="utf-8")) == report


def test_cli_run_includes_contract_evidence_for_successful_nodes():
    result = _run_cli(
        "run",
        TEXT_INPUT_WORKFLOW,
        "--target-node",
        "98",
    )

    assert result.returncode == 0, result.stderr
    report = _json(result.stdout)
    assert report["status"] == "ok"
    assert report["contract_evidence"]["98"]["passed"] is True
    assert report["runtime_result"]["node_results"]["98"]["contract_evidence"]["passed"] is True
    assert report["runtime_result"]["node_results"]["98"]["outputs"]["Output"]["row_count"] == 6


def test_cli_run_override_error_preserves_structured_context(tmp_path):
    result = _run_cli(
        "run",
        TEXT_INPUT_WORKFLOW,
        "--target-node",
        "98",
        "--override-output",
        "bad",
    )

    assert result.returncode == 2
    report = _json(result.stdout)
    assert report["status"] == "error"
    assert report["workflow"]["workflow_name"] == "Text_Input"
    assert report["target_node"] == "98"
    assert report["output_overrides"] == {"bad": ""}
    assert report["error"]["type"] == "ValueError"
    assert "--override-output must use NODE_ID=PATH" in report["error"]["message"]
    assert report["trace"]["traces"] == []


def test_cli_certify_post_run_error_preserves_structured_context():
    result = _run_cli(
        "certify",
        TEXT_INPUT_WORKFLOW,
        "--target-node",
        "98",
        "--expect",
        COMBINE_EXPECTED,
    )

    assert result.returncode == 2
    report = _json(result.stdout)
    assert report["status"] == "error"
    assert report["workflow"]["workflow_name"] == "Text_Input"
    assert report["target_node"] == "98"
    assert report["output_overrides"] == {}
    assert report["error"]["type"] == "ValueError"
    assert "--actual is required" in report["error"]["message"]
    assert report["trace"]["traces"][0]["node_id"] == "98"
