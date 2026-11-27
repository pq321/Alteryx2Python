from itertools import combinations, product
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

from alteryx2python.parity.archetype_datasets import build_archetype, derive_universal_perturbations
from alteryx2python.parity.canvas_packer import CanvasCase, pack_tool_configurations, pairwise_cases
from alteryx2python.parity.schema_registry import extract_tool_schema
from alteryx2python.parity.sensitivity import NonDiscriminatingDatasetError, verify_config_sensitivity


def test_schema_does_not_treat_observed_values_as_an_enum(tmp_path):
    (tmp_path / "bin").mkdir()
    sample = tmp_path / "Samples" / "sample.yxmd"
    sample.parent.mkdir()
    sample.write_text(
        '<AlteryxDocument><Nodes><Node ToolID="1">'
        '<GuiSettings Plugin="AlteryxBasePluginsGui.RecordID.RecordID"/>'
        '<Properties><Configuration><StartValue>7</StartValue></Configuration></Properties>'
        '</Node></Nodes></AlteryxDocument>',
        encoding="utf-8",
    )

    schema = extract_tool_schema("RecordID", tmp_path).to_dict()
    assert schema["axes"]["Configuration/StartValue"] == {"observed": ["7"], "declared": []}
    assert schema["unresolved"]


def test_pairwise_covers_only_declared_domains():
    axes = {"aggregation": ("sum", "count", "average"), "retain": ("yes", "no"), "separator": (",", "|")}
    cases = pairwise_cases(axes)
    assert len(cases) < 12
    for left, right in combinations(axes, 2):
        assert {(case[left], case[right]) for case in cases} == set(product(axes[left], axes[right]))


def test_tabular_canvas_shares_the_input_and_keeps_case_nodes_distinct(tmp_path):
    bundle = build_archetype("D03", tmp_path / "data")
    variants = [
        CanvasCase(f"start-{value}", f'<Configuration><FieldName>ID</FieldName><StartValue>{value}</StartValue>'
                   "<FieldType>Int32</FieldType></Configuration>")
        for value in (1, 7)
    ]
    packed = pack_tool_configurations("RecordID", variants, bundle, workflow_path=tmp_path / "shared.yxmd")
    assert len(set(packed.case_nodes.values())) == 2
    assert packed.workflow.is_file()
    canvas = ET.parse(packed.workflow)
    assert len(canvas.findall("./Nodes/Node")) == 3
    assert len({edge.get("ToolID") for edge in canvas.findall("./Connections/Connection/Origin")}) == 1
    assert bundle.files["input"].read_text(encoding="utf-8").splitlines()[:3] == ['"text"', "", '""']
    perturbed = derive_universal_perturbations(bundle)
    assert perturbed["P_EMPTY_0ROW"].tables["input"].empty
    assert perturbed["P_ALL_NULL_COL"].tables["input"]["text"].isna().all()


def test_sensitivity_rejects_identical_values_and_accepts_a_changed_anchor():
    base = {"status": "success", "outputs": {"Output": pd.DataFrame({"id": [1, 2]})}}
    with pytest.raises(NonDiscriminatingDatasetError):
        verify_config_sensitivity("RecordID", base, base, "D03")
    variant = {"status": "success", "outputs": {"Output": pd.DataFrame({"id": [7, 8]})}}
    assert verify_config_sensitivity("RecordID", base, variant, "D03").changed_anchors == ("Output",)


def test_loopback_services_capture_requests_and_attachments():
    from email.message import EmailMessage
    from hashlib import sha256
    from smtplib import SMTP
    from urllib.request import Request, urlopen

    from alteryx2python.parity.loopback_services import HttpResponse, LocalHttpTestServer, LocalSmtpCaptureServer

    with LocalHttpTestServer({("POST", "/test"): HttpResponse(200, b'{"ok": true}', {"X-Parity": "yes"})}) as http:
        request = Request(http.url + "/test", method="POST", data=b"<test/>")
        with urlopen(request, timeout=2) as response:
            assert response.headers["X-Parity"] == "yes"
            assert response.read() == b'{"ok": true}'
        assert http.requests[0]["body"] == b"<test/>"
    with LocalSmtpCaptureServer() as smtp:
        message = EmailMessage()
        message["From"], message["To"] = "sender@example.test", "receiver@example.test"
        message.set_content("<p>Report</p>", subtype="html")
        message.add_attachment(b'\x00\xff', maintype="application", subtype="octet-stream", filename="raw.bin")
        with SMTP("127.0.0.1", smtp.port, local_hostname="parity.test", timeout=5) as client:
            client.send_message(message)
        assert smtp.messages[0]["attachments"] == [{"filename": "raw.bin", "sha256": sha256(b'\x00\xff').hexdigest()}]


def test_command_fixture_captures_arguments_and_exit_code():
    import json
    import subprocess

    from alteryx2python.parity.loopback_services import IsolatedCommandSandbox

    with IsolatedCommandSandbox() as sandbox:
        reply = subprocess.run(sandbox.arguments(7, ['space & "quotes"']), cwd=sandbox.directory, capture_output=True)
        assert reply.returncode == 7
        assert json.loads((sandbox.directory / "command-output.json").read_text()) == ['space & "quotes"']


def test_workbook_comparison_tracks_cells_and_ignores_package_metadata(tmp_path):
    from openpyxl import Workbook

    from alteryx2python.parity.runner import comparable_artifact, file_hash

    def save(name, title, formula):
        workbook = Workbook()
        workbook.properties.title = title
        workbook.active.append(["id", "result"])
        workbook.active.append([1, formula])
        path = tmp_path / name
        workbook.save(path)
        return path

    native = save("actual.xlsx", "Designer Report", "=A2+1")
    other = save("converted.xlsx", "Python Report", "=A2+1")
    wrong = save("changed.xlsx", "Python Report", "=A2+2")
    assert file_hash(native) != file_hash(other)
    assert comparable_artifact(native) == comparable_artifact(other)
    assert comparable_artifact(native) != comparable_artifact(wrong)
