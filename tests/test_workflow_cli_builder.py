import json
from pathlib import Path
from xml.etree import ElementTree as ET

from alteryx2python.cli import main
from alteryx2python.workflow_spec import WorkflowSpec, NodeSpec, EdgeSpec


def invoke(capsys, *args):
    code = main(list(map(str, args)))
    return code, json.loads(capsys.readouterr().out)


def test_cli_build_edit_extract_export_and_run_graph(tmp_path, capsys):
    spec = WorkflowSpec(
        [
            NodeSpec(
                "1",
                "TextInput",
                '<Fields><Field name="x"/></Fields><Data><r><c>2</c></r></Data>',
            )
        ]
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(spec.to_json(), encoding="utf-8")
    native, python = tmp_path / "workflow.yxmd", tmp_path / "workflow.py"
    code, report = invoke(
        capsys,
        "generate-workflow",
        "--spec",
        spec_path,
        "--output",
        native,
        "--python-output",
        python,
    )
    assert code == 0 and python.is_file()
    import subprocess, sys

    generated_results = tmp_path / "generated-results"
    direct = subprocess.run(
        [sys.executable, str(python), "--output-dir", str(generated_results)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert direct.returncode == 0, direct.stderr
    assert (
        json.loads(
            (generated_results / "python-results/capture.json").read_text(
                encoding="utf-8"
            )
        )["status"]
        == "success"
    )
    node_path = tmp_path / "formula.json"
    node_path.write_text(
        json.dumps(
            {
                "node_id": "2",
                "tool_type": "Formula",
                "configuration_xml": '<FormulaFields><FormulaField field="y" expression="[x] * 3" type="Int64"/></FormulaFields>',
            }
        ),
        encoding="utf-8",
    )
    edited = tmp_path / "edited.yxmd"
    code, _ = invoke(
        capsys,
        "workflow-edit",
        native,
        "--add-node",
        node_path,
        "--connect",
        "1:Output=2:Input",
        "--output",
        edited,
    )
    assert code == 0
    code, report = invoke(capsys, "validate-workflow", edited, "--require-executable")
    assert code == 0 and report["graph_valid"] and not report["native_semantics_proven"]
    exported = tmp_path / "export.json"
    assert invoke(capsys, "workflow-export", edited, "--output", exported)[0] == 0
    template = tmp_path / "node.json"
    assert (
        invoke(capsys, "node-template", edited, "--node", "2", "--output", template)[0]
        == 0
    )
    assert "FormulaField" in json.loads(template.read_text())["template_xml"]
    run_dir = tmp_path / "run"
    code, report = invoke(capsys, "run-python", edited, "--output-dir", run_dir)
    assert code == 0 and report["status"] == "success"
    capture = json.loads(
        (run_dir / "python-results/capture.json").read_text(encoding="utf-8")
    )
    assert capture["nodes"]["2"]["outputs"]["Output"]["rows"][0][1]["value"] == "6"
    removed = tmp_path / "removed.yxmd"
    assert (
        invoke(
            capsys, "workflow-edit", edited, "--remove-node", "2", "--output", removed
        )[0]
        == 0
    )
    assert len(ET.parse(removed).getroot().findall("Nodes/Node")) == 1


def test_cli_question_configuration_and_generated_execution(tmp_path, capsys):
    from test_app_config import app_xml

    app = tmp_path / "app.yxwz"
    app.write_text(app_xml(), encoding="utf-8")
    answers = tmp_path / "answers.json"
    answers.write_text('{"factor":5}', encoding="utf-8")
    code, report = invoke(capsys, "questions", app)
    assert code == 0 and report["questions"][0]["name"] == "factor"
    configured = tmp_path / "configured.yxwz"
    assert (
        invoke(
            capsys,
            "configure-workflow",
            app,
            "--answers",
            answers,
            "--output",
            configured,
        )[0]
        == 0
    )
    assert ET.parse(configured).find(".//FormulaField").get("expression") == "[x] * 5"
    assert (
        invoke(
            capsys,
            "run-python",
            configured,
            "--output-dir",
            tmp_path / "configured-results",
        )[0]
        == 0
    )
    generated = tmp_path / "app.py"
    assert (
        invoke(capsys, "generate", app, "--answers", answers, "--output", generated)[0]
        == 0
    )
    namespace = {}
    exec(generated.read_text(encoding="utf-8"), namespace)
    result, _ = namespace["run_workflow"]()
    assert result.node_results["2"].outputs["Output"]["result"].tolist() == [10, 25]


def test_cli_blocked_suite_and_per_node_never_exit_success(
    tmp_path, capsys, monkeypatch
):
    import alteryx2python.cli as cli

    monkeypatch.setattr(
        cli,
        "run_equivalence_suite",
        lambda *a, **kw: {
            "summary": {"equivalent": 0, "mismatched": 0, "native_blocked": 10}
        },
    )
    assert invoke(capsys, "equivalence-suite", "--out-dir", tmp_path / "suite")[0] == 2
    assert invoke(capsys, "equivalence", "missing.yxmd", "--per-node")[0] == 2


def test_cli_tools_and_unavailable_report(tmp_path, capsys):
    output = tmp_path / "tools.json"
    code, report = invoke(capsys, "tools", "--output", output)
    assert code == 0 and report["mapped_unique_ids"] == 321
    assert len(report["tools"]) == report["official_rows"]
    assert invoke(capsys, "tools", "--tool", "not_a_tool")[0] == 2
    unknown = WorkflowSpec(
        [
            NodeSpec(
                "1",
                "Custom",
                plugin_id="MyPlugin",
                engine_dll="mine.dll",
                engine_entry="main",
                input_anchors=(),
                output_anchors=(),
            )
        ]
    )
    native = tmp_path / "unknown.yxmd"
    native.write_text(unknown.to_xml(), encoding="utf-8")
    code, report = invoke(capsys, "validate-workflow", native, "--require-executable")
    assert code == 2 and report["unsupported_nodes"]


def test_invalid_edit_does_not_overwrite_existing_destination(tmp_path, capsys):
    native = tmp_path / "workflow.yxmd"
    native.write_text(
        WorkflowSpec([NodeSpec("1", "TextInput")]).to_xml(), encoding="utf-8"
    )
    output = tmp_path / "output.yxmd"
    output.write_text("preserve", encoding="utf-8")
    code, _ = invoke(
        capsys,
        "workflow-edit",
        native,
        "--connect",
        "1:Output=999:Input",
        "--output",
        output,
    )
    assert code == 2 and output.read_text(encoding="utf-8") == "preserve"
