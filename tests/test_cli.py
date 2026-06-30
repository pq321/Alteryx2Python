import json
import subprocess
import sys
from pathlib import Path


COMBINE_WORKFLOW = "D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd"
COMBINE_EXPECTED = "tests/fixtures/real_workflows/combine_customer_profile_expected.csv"
TEXT_INPUT_WORKFLOW = "D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/01 In Out/Text_Input.yxmd"
NORMALIZE_STRING_WORKFLOW = "D:/Alteryx/Samples/en/04 Basic/01 Normalize_a_string_field.yxmd"
XML_PARSE_WORKFLOW = "D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/04 Parse/XML_Parse.yxmd"
DYNAMIC_INPUT_WORKFLOW = "D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/22 Developer/Dynamic_Input.yxmd"
W1_WORKFLOW = "examples/sample_workflows/w1.yxmd"


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
    assert "support_map" in report
    assert "nodes" not in report


def test_cli_support_map_reports_change_request_surfaces():
    result = _run_cli("support-map", W1_WORKFLOW)

    assert result.returncode == 0, result.stderr
    report = _json(result.stdout)
    assert report["status"] == "ok"
    support_map = report["support_map"]
    assert support_map["format"] == "alteryx2python.support_map"
    assert support_map["change_request_index"]["inputs"] == []
    assert support_map["change_request_index"]["outputs"] == ["5"]
    assert support_map["change_request_index"]["attachment_candidates"] == ["5"]


def test_cli_generate_writes_python_script_and_manifest(tmp_path):
    output_path = tmp_path / "w1.py"
    log_path = tmp_path / "generate.json"

    result = _run_cli("generate", W1_WORKFLOW, "--output", str(output_path), "--log", str(log_path))

    assert result.returncode == 0, result.stderr
    report = _json(result.stdout)
    assert report["status"] == "ok"
    assert report["command"] == "generate"
    assert report["output"] == str(output_path)
    assert report["workflow"]["workflow_name"] == "w1"
    assert "def run_workflow(runtime_config=None, initial_inputs=None, target_node_ids=None):" in output_path.read_text(
        encoding="utf-8"
    )
    assert json.loads(log_path.read_text(encoding="utf-8")) == report


def test_cli_generate_samples_writes_python_scripts_for_directory(tmp_path):
    output_dir = tmp_path / "generated"

    result = _run_cli("generate-samples", "examples/sample_workflows", "--output-dir", str(output_dir))

    assert result.returncode == 0, result.stderr
    report = _json(result.stdout)
    assert report["status"] == "ok"
    assert report["workflow_count"] == 2
    assert report["generated_count"] == 2
    generated_outputs = {Path(item["output"]).name for item in report["generated"]}
    assert generated_outputs == {"MIFID II.py", "w1.py"}
    assert (output_dir / "w1.py").exists()
    assert report["unsupported_tool_types"] == {}


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


def test_cli_run_records_dynamicinput_baseline_success(tmp_path):
    log_path = tmp_path / "dynamicinput.json"

    result = _run_cli(
        "run",
        DYNAMIC_INPUT_WORKFLOW,
        "--target-node",
        "52",
        "--log",
        str(log_path),
    )

    assert result.returncode == 0
    report = _json(result.stdout)
    assert report["status"] == "ok"
    assert report["workflow"]["source_file"].endswith("Dynamic_Input.yxmd")
    assert report["target_node"] == "52"
    assert report["output_overrides"] == {}
    assert report["context_errors"] == []
    assert report["runtime_result"]["node_results"]["52"]["tool_type"] == "DynamicInput"
    assert (
        report["runtime_result"]["node_results"]["52"]["trace"]["config"]["external_input_read_performed"]
        is False
    )
    assert report["runtime_result"]["node_results"]["52"]["outputs"]["Output"]["row_count"] == 1
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


def test_cli_run_executes_w1_cleanse_macro_mapping(tmp_path):
    output_path = tmp_path / "w1-output.csv"

    result = _run_cli(
        "run",
        W1_WORKFLOW,
        "--target-node",
        "5",
        "--override-output",
        f"5={output_path}",
    )

    assert result.returncode == 0, result.stderr
    report = _json(result.stdout)
    assert report["status"] == "ok"
    assert report["execution_order"] == ["2", "3", "4", "5"]
    assert report["outputs"]["4"]["Output26"]["row_count"] == 3
    assert report["outputs"]["4"]["Output26"]["columns"] == ["rename_col2", "col1", "col3"]
    assert output_path.read_text(encoding="utf-8").splitlines() == [
        "rename_col2,col1,col3",
        "3,1,",
        "4,2,ok",
        "5,3,okay",
    ]


def test_cli_run_reports_support_diagnostics_for_schema_drift(tmp_path):
    workflow_path = tmp_path / "schema_drift.yxmd"
    workflow_text = Path(W1_WORKFLOW).read_text(encoding="utf-8")
    workflow_path.write_text(
        workflow_text.replace('field="col2"', 'field="col_2"', 1),
        encoding="utf-8",
    )

    result = _run_cli("run", str(workflow_path), "--target-node", "3")

    assert result.returncode == 2
    report = _json(result.stdout)
    assert report["status"] == "error"
    diagnostic = report["diagnostics"][0]
    assert diagnostic["code"] == "missing_input_fields"
    assert diagnostic["node"]["id"] == "3"
    assert diagnostic["node"]["tool_type"] == "Select"
    assert diagnostic["missing_fields"] == ["col_2"]
    assert "col2" in diagnostic["field_suggestions"]["col_2"]
    assert diagnostic["inputs"]["Input"]["columns"] == ["col1", "col2", "col3"]
    assert diagnostic["graph_context"]["incoming"] == [
        {
            "id": "2:Output->3:Input",
            "from": "2:Output",
            "to": "3:Input",
            "source_tool_type": "TextInput",
        }
    ]
    assert report["trace"]["traces"][-1]["node_id"] == "3"
    assert report["trace"]["traces"][-1]["status"] == "failed"


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
