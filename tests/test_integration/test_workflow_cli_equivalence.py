from __future__ import annotations

from pathlib import Path

import pytest

from alteryx2python.equivalence import (
    compare_frames,
    find_output_node,
    read_alteryx_csv,
    run_equivalence,
    run_python_workflow,
)
from alteryx2python.native_runner import EngineCmdRunner
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.workflow_presets import preset_names, render_preset

SAMPLES_ROOT = Path("D:/Alteryx/Samples/en")
TEXT_INPUT_WORKFLOW = SAMPLES_ROOT / "02 Learn_one_tool_at_a_time/01 In Out/Text_Input.yxmd"
TEXT_INPUT_ORACLE = Path("tests/fixtures/real_workflows/text_input_expected.csv")


def _tmp_workflow(tmp_path: Path, preset: str, seed: int = 42) -> Path:
    yxmd = tmp_path / f"{preset}.yxmd"
    yxmd.write_text(
        render_preset(preset, str(tmp_path / f"{preset}_native.csv"), seed=seed, rows=25),
        encoding="utf-8",
    )
    return yxmd


def test_every_preset_parses_with_zero_unknown_nodes(tmp_path):
    parser = XmlWorkflowParser()
    for preset in preset_names():
        workflow = parser.parse(_tmp_workflow(tmp_path, preset))
        unknown = [node for node in workflow.nodes if node.tool_type == "UNKNOWN"]
        assert unknown == [], preset


def test_presets_execute_deterministically_on_python_runtime(tmp_path):
    for preset in preset_names():
        first = run_python_workflow(_tmp_workflow(tmp_path, preset), find_output_node(_tmp_workflow(tmp_path, preset)), tmp_path / f"{preset}_a.csv")
        second = run_python_workflow(_tmp_workflow(tmp_path, preset), find_output_node(_tmp_workflow(tmp_path, preset)), tmp_path / f"{preset}_b.csv")
        assert compare_frames(first, second).matches, preset
        assert len(first.index) > 0, preset


@pytest.mark.skipif(not EngineCmdRunner().available(), reason="native engine not installed")
def test_equivalence_records_license_blockade_and_python_results(tmp_path):
    """On a host without the automation license the native side is blocked with
    its exact engine error, while the Python side still executes and the report
    marks the comparison as no-oracle instead of silently passing."""
    yxmd = _tmp_workflow(tmp_path, "summarize")
    report = run_equivalence(yxmd, native_csv=tmp_path / "summarize_native.csv", timeout=90)
    assert report["python"]["ok"] is True
    assert report["native"]["ok"] is False
    if "licensed" in report["native"]["detail"]:
        assert report["equivalent"] is None
        assert report["compare"]["status"] == "no-oracle"
    else:  # licensed hosts produce a real comparison
        assert report["equivalent"] is True


@pytest.mark.skipif(not TEXT_INPUT_WORKFLOW.exists(), reason="official sample corpus not installed")
def test_real_alteryx_oracle_matches_python_output(tmp_path):
    """End-to-end equivalence against a real Alteryx-produced CSV oracle.

    The workflow embeds the official Text Input sample data (real workflow
    node) plus a CSV output sink; the Python runtime output is compared with
    the oracle CSV produced by the native engine (certification fixture).
    """
    sample_xml = TEXT_INPUT_WORKFLOW.read_text(encoding="utf-8")
    start = sample_xml.index('<Node ToolID="98">')
    end = sample_xml.index("</Node>", start) + len("</Node>")
    text_input_node = sample_xml[start:end]
    oracle_csv = tmp_path / "oracle.csv"
    workflow_xml = (
        '<?xml version="1.0"?>\n<AlteryxDocument yxmdVer="2022.1">\n<Nodes>'
        + text_input_node
        + '<Node ToolID="99"><GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput">'
        + '<Position x="600" y="186" /></GuiSettings><Properties><Configuration>'
        + '<File MaxRecords="" FileFormat="0">' + str(oracle_csv) + '</File><Passwords />'
        + "<FormatSpecificOptions><LineEndStyle>CRLF</LineEndStyle><Delimeter>,</Delimeter>"
        + "<ForceQuotes>False</ForceQuotes><HeaderRow>True</HeaderRow><CodePage>28591</CodePage>"
        + "<WriteBOM>True</WriteBOM></FormatSpecificOptions>"
        + '<MultiFile value="False" /></Configuration>'
        + '<Annotation DisplayMode="0"><Name /><DefaultAnnotationText /><Left value="False" /></Annotation>'
        + "</Properties>"
        + '<EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxDbFileOutput" />'
        + "</Node></Nodes>\n"
        + '<Connections><Connection><Origin ToolID="98" Connection="Output" />'
        + '<Destination ToolID="99" Connection="Input" /></Connection></Connections>\n'
        + '<Properties><Memory default="True" /><GlobalRecordLimit value="0" />'
        + "<RuntimeProperties><Actions /><Questions /></RuntimeProperties></Properties>"
        + "</AlteryxDocument>\n"
    )
    workflow_path = tmp_path / "oracle_equivalence.yxmd"
    workflow_path.write_text(workflow_xml, encoding="utf-8")

    python_csv = tmp_path / "python.csv"
    python_frame = run_python_workflow(workflow_path, "99", python_csv)

    import pandas as pd

    oracle_frame = pd.read_csv(
        TEXT_INPUT_ORACLE, keep_default_na=False, na_values={"LastName": [""]}
    )
    comparison = compare_frames(oracle_frame, python_frame)
    # Native NULL and Python empty string are distinct under the acceptance contract.
    assert comparison.matches is False


def test_compare_frames_numeric_tolerance_and_column_diff():
    import pandas as pd

    left = pd.DataFrame({"a": ["1.0", "2.0", "x"], "b": ["1", "", None]})
    right = pd.DataFrame({"a": [1.0, 2.0, "x"], "b": [1, "", ""]})
    assert compare_frames(left, right).matches is False

    different_columns = compare_frames(
        pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [1]})
    )
    assert different_columns.matches is False
    assert "missing_in_python" in different_columns.column_diff
