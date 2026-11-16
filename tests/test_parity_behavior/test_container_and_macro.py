import json
import os
from pathlib import Path
from shutil import copyfile
from xml.etree import ElementTree as ET

import pytest

from alteryx2python.parity.macro_replay import prepare_macro_replay
from alteryx2python.parity.manual import attest_native
from alteryx2python.parity.runner import collect_native, compare_runs, prepare
from alteryx2python.parity.samples import generate_container_macro_samples, generate_variable_event_sample
from alteryx2python.parity.scope import phase_one_scope
from alteryx2python.workflow_generator import WorkflowBuilder


NATIVE_TEXT = Path("tests/fixtures/parity/native_textinput.yxdb")


def test_nested_container_probe_placement_and_macro_invocations(tmp_path):
    enabled, disabled = generate_container_macro_samples(tmp_path / "fixtures")
    open_dir, closed_dir = tmp_path / "open", tmp_path / "closed"
    opened, closed = prepare(enabled, open_dir), prepare(disabled, closed_dir)
    tree = ET.parse(open_dir / "instrumented.yxmd")
    children = tree.find(".//Node[@ToolID='5']/ChildNodes")
    macros = [p["probe_id"] for p in opened["probes"] if p["node_id"] == "6"]
    assert macros and children.find(f"Node[@ToolID='{macros[0]}']") is not None
    assert {p["node_id"] for p in closed["probes"]} == {"1", "2"}
    disabled_xml = ET.parse(closed_dir / "instrumented.yxmd")
    assert Path(disabled_xml.find(".//Node[@ToolID='6']/EngineSettings").get("Macro")) == disabled.parent / "NestedMultiply.yxmc"
    assert len(opened["macro_dependencies_sha256"]) == 2
    python = json.loads((open_dir / "python.json").read_text(encoding="utf8"))
    outer = python["macro_invocations"]["6"]["1"]
    inner = outer["macro_invocations"]["2"]["1"]["nodes"]
    assert inner["1"]["inputs"]["Input"]["rows"] == [[{"kind": "int", "value": "6"}]]
    assert python["nodes"]["6"]["outputs"]["Output"]["rows"] == [[{"kind": "int", "value": "18"}]]
    python = json.loads((closed_dir / "python.json").read_text(encoding="utf8"))
    assert python["nodes"]["6"]["status"] == "skipped"
    assert python["nodes"]["6"]["outputs"] == {}
    assert python["macro_invocations"] == {}
    with pytest.raises(ValueError, match="missing native output"):
        attest_native(open_dir, "success")

    for probe in closed["probes"]:
        copyfile(NATIVE_TEXT, closed_dir / probe["file"])
    attest_native(closed_dir, "success")
    native = collect_native(closed_dir)
    assert all(native["nodes"][node_id]["status"] == "skipped" for node_id in ("3", "5", "6"))
    report = compare_runs(native, python)
    assert {item["node_id"] for item in report["comparisons"] if item["status"] == "skipped"} == {"3", "5", "6"}
    python["nodes"]["6"]["status"] = "success"
    assert "node_6_skip_mismatch" in compare_runs(native, python)["issues"]


def test_disabled_container_does_not_require_its_macro_files(tmp_path):
    enabled, disabled = generate_container_macro_samples(tmp_path / "fixtures")
    (enabled.parent / "NestedMultiply.yxmc").unlink()
    closed_dir = tmp_path / "closed"
    manifest = prepare(disabled, closed_dir)
    assert manifest["macro_dependencies_sha256"] == {}
    python = json.loads((closed_dir / "python.json").read_text(encoding="utf8"))
    assert python["status"] == "success"
    assert python["nodes"]["6"]["status"] == "skipped"
    with pytest.raises(ValueError, match="Macro dependency is unavailable"):
        prepare(enabled, tmp_path / "open")


@pytest.mark.parametrize(("answers", "results"), [
    (None, ["4", "10"]),
    ({"factor": 4}, ["8", "20"]),
    ({"factor": 11}, None),
])
def test_analytic_app_preserves_actions_for_designer_and_uses_supplied_python_answers(tmp_path, answers, results):
    app = Path("examples/cli/parameter-app.yxwz")
    run = tmp_path / "app"
    manifest = prepare(app, run, answers=answers)
    instrumented = ET.parse(run / "instrumented.yxwz")
    action = instrumented.find("Properties/RuntimeProperties/Actions/NoCondition/True/Action")
    assert action.find("ToolId").get("value") == "4"
    assert instrumented.find("Nodes/Node[@ToolID='4']/EngineSettings") is None
    assert instrumented.find("Properties/RuntimeProperties/Questions") is not None
    formula = instrumented.find(".//FormulaField")
    assert formula.get("size") == "8"
    assert formula.get("expression") == "[x] * (2)"
    select_fields = instrumented.findall(".//SelectField")
    assert [(f.get("field"), f.get("type"), f.get("size")) for f in select_fields[:2]] == [
        ("x", "Byte", "1"), ("result", "Int64", "8"),
    ]
    assert set(node["node_id"] for node in manifest["nodes"]) == {"1", "2", "6"}
    python = json.loads((run / "python.json").read_text(encoding="utf8"))
    assert python["answers"] == answers
    if results is None:
        assert python["status"] == "failed"
        assert "answer outside numeric bounds: factor" in python["failure"]["message"]
        assert python["nodes"]["2"]["outputs"] == {}
    else:
        assert python["status"] == "success"
        assert [row[-1]["value"] for row in python["nodes"]["2"]["outputs"]["Output"]["rows"]] == results
        assert [row[-1]["value"] for row in python["nodes"]["6"]["outputs"]["Output"]["rows"]] == results


def test_builder_writes_sizes_for_formula_and_typed_select():
    builder = WorkflowBuilder()
    builder.add_formula([("result", "Int64", "", "2")])
    builder.add_select(
        [("result", "True"), ("label", "True")],
        field_types={"result": ("Int64", None), "label": ("V_WString", 64)},
    )
    root = ET.fromstring(builder.render())

    assert root.find(".//FormulaField").get("size") == "8"
    assert [field.get("size") for field in root.findall(".//SelectField")] == ["8", "64", None]


def test_macro_replay_uses_attested_yxdb_and_preserves_caller(tmp_path):
    enabled, _ = generate_container_macro_samples(tmp_path / "fixtures")
    source = ET.parse(enabled)
    nodes = source.find("Nodes")
    text = nodes.find("Node[@ToolID='1']")
    macro = nodes.find(".//Node[@ToolID='6']")
    config = text.find("Properties/Configuration")
    fixture = ET.parse("examples/parity/branch_duplicates_unicode.yxmd")
    text.find("Properties").remove(config)
    text.find("Properties").append(fixture.find(".//Node[@ToolID='1']/Properties/Configuration"))
    settings = macro.find("EngineSettings")
    settings.set("Macro", "Identity.yxmc")
    identity = ET.parse(enabled.parent / "Multiply.yxmc")
    identity.find("Nodes").remove(identity.find(".//Node[@ToolID='2']"))
    edges = identity.find("Connections")
    edges.remove(edges[0])
    edges[0].find("Origin").set("ToolID", "1")
    identity.write(enabled.parent / "Identity.yxmc", encoding="utf-8")
    nodes[:] = [text, macro]
    edges = source.find("Connections")
    edges[:] = [edges[0]]
    edges[0].find("Destination").set("ToolID", "6")
    source.write(enabled, encoding="utf-8")

    capture = tmp_path / "capture"
    manifest = prepare(enabled, capture)
    for probe in manifest["probes"]:
        copyfile(NATIVE_TEXT, capture / probe["file"])
    attest_native(capture, "success")
    replay = tmp_path / "replay"
    report = prepare_macro_replay(capture, "6", replay)
    assert report["status"] == "match"
    assert report["inputs"][0]["source"] == ("1", "Output")
    wrapper = ET.parse(replay / "replay.yxmd")
    assert wrapper.find(".//Node[@ToolID='6']/EngineSettings").get("Macro").endswith("Identity.yxmc")


def test_screenshot_scope_has_unique_registered_ids():
    report = phase_one_scope()
    assert len({row["tool_type"] for row in report["tools"]}) == report["tool_count"] == 95
    assert all(row["config_parser"] and row["runtime_profile"] != "unregistered" for row in report["tools"])


def test_fixed_output_file_requires_separate_artifact_evidence(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["x"], [["2"]])
    sink = builder.add_csv_output(str(tmp_path / "original.csv"))
    builder.connect(source, sink)
    workflow = tmp_path / "sink.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    directory = tmp_path / "run"
    manifest = prepare(workflow, directory)
    copyfile(NATIVE_TEXT, directory / manifest["probes"][0]["file"])
    with pytest.raises(ValueError, match="missing native sink"):
        attest_native(directory, "success")
    native_file = directory / manifest["sink_files"][str(sink)]
    native_file.write_bytes(b"different")
    attest_native(directory, "success")
    python = json.loads((directory / "python.json").read_text(encoding="utf-8"))
    assert str(sink) in python["sink_artifacts"]
    assert "sink_artifacts_mismatch" in compare_runs(collect_native(directory), python)["issues"]
    assert not (tmp_path / "original.csv").exists()


@pytest.mark.parametrize("right", [False, True])
def test_detour_captures_only_the_active_route(tmp_path, right):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["x"], [["2"]])
    detour = builder._node("Detour", f'<DetourRight value="{right}"/>', (200, 100))
    inactive = builder.add_formula([("x", "Int64", "8", "[missing] + 1")])
    end = builder._node("DetourEnd", "", (300, 100))
    left, right_port = ("Right", "Left") if right else ("Left", "Right")
    builder.connect(source, detour)
    builder.connect(detour, end, left, left)
    builder.connect(detour, inactive, right_port)
    builder.connect(inactive, end, "Output", right_port)
    workflow = tmp_path / "detour.yxmd"
    workflow.write_text(builder.render(), encoding="utf-8")
    directory = tmp_path / "capture"
    result = prepare(workflow, directory)
    anchors = {p["anchor"] for p in result["probes"] if p["node_id"] == str(detour)}
    assert anchors == {left}
    assert next(n for n in result["nodes"] if n["node_id"] == str(inactive))["skip_reason"] == "detour_inactive"
    capture = json.loads((directory / "python.json").read_text())
    assert capture["status"] == "success"
    assert capture["nodes"][str(inactive)]["status"] == "skipped"
    assert capture["nodes"][str(end)]["outputs"]["Output"]["rows"] == [[{"kind": "int", "value": "2"}]]


@pytest.mark.skipif(os.name != "nt", reason="Windows command-event fixture")
def test_workflow_event_artifacts_and_workflow_variables(tmp_path):
    source, = generate_variable_event_sample(tmp_path / "events-source")
    command = source.parent / "record-event.cmd"
    directory = tmp_path / "events-run"
    with pytest.raises(ValueError, match="isolated workflow event test case"):
        prepare(source, directory)
    manifest = prepare(source, directory, event_commands=(str(command),))
    assert list(manifest["event_commands_sha256"]) == [str(command)]
    python = json.loads((directory / "python.json").read_text(encoding="utf-8"))
    assert (directory / "python-outputs/events/events.txt").read_text().splitlines() == ["before", "success", "after"]
    results = python["nodes"]["2"]["outputs"]["Output"]["rows"]
    assert [[col["value"] for col in row[1:]] for row in results] == [["6", "parity"], ["15", "parity"]]

    for probe in manifest["probes"]:
        copyfile(NATIVE_TEXT, directory / probe["file"])
    marker = directory / "native-events/events.txt"
    marker.write_text("different", encoding="utf-8")
    attest_native(directory, "success")
    assert "event_artifacts_mismatch" in compare_runs(collect_native(directory), python)["issues"]
    marker.write_text("changed after attestation", encoding="utf-8")
    with pytest.raises(ValueError, match="Native event artifacts changed"):
        collect_native(directory)
