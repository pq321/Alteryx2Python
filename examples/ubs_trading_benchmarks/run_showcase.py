"""Run the synthetic benchmarks in Designer and the generated Python packages."""

from argparse import ArgumentParser
from contextlib import ExitStack
from decimal import Decimal, InvalidOperation
from email import policy
from email.parser import BytesParser
from html import escape
from html.parser import HTMLParser
from io import BytesIO
from math import isclose
from pathlib import Path
import json
import runpy
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET

import pandas as pd

from alteryx2python.generator.package_compiler import ModularPackageGenerator
from alteryx2python.generator.python_generator import PythonGenerator
from alteryx2python.generator.readable import read_phase_one
from alteryx2python.parity.amp_export import prepare_amp_export
from alteryx2python.parity.loopback_services import HttpResponse, LocalHttpTestServer, LocalSmtpCaptureServer
from alteryx2python.parity.manual import attest_native
from alteryx2python.parity.runner import capture_python, collect_native, compare_runs, file_hash, prepare, write_json
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from prepare_datasets import ROOT, SCENARIOS, equities, mifid, positions, surveillance


TITLES = ("Equities & FX reconciliation", "Trade surveillance", "Multi-region position risk", "MiFID II reporting")
WORKBOOKS = ("trade_recon_pack.xlsx", "surveillance_breach_alerts.csv",
             "consolidated_positions.xlsx", "MIFID output.xlsx")
REPORTS = ("desk_pnl_daily_report.html", "compliance_alert_body.html", "global_position_risk.html", None)
STYLE = """
body{margin:0;background:#f3f5f7;color:#17283b;font:15px system-ui,sans-serif}
main{max-width:1500px;margin:auto;padding:38px 4vw 80px}
h1{font-size:2.35rem;line-height:1.12;margin-top:0}
a{color:#175b91} .cards,.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
article,.sheet{background:white;border:1px solid #dce2e7;border-radius:12px;padding:20px;margin-bottom:16px}
.sheet{overflow:auto}.match{color:#176843}.gap,.different{color:#8d3020;background:#fff0eb}
table{border-collapse:collapse;font-size:13px;white-space:nowrap}th,td{padding:6px 9px;border-bottom:1px solid #dce2e7;text-align:left}
th{background:#edf2f6} iframe{width:100%;height:300px;border:1px solid #dce2e7}
@media(max-width:760px){.cards,.pair{grid-template-columns:1fr}}
"""


def page(path, title, body):
    path.write_text(
        f'<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width"><title>{escape(title)}</title>'
        f'<style>{STYLE}</style><main><h1>{escape(title)}</h1>{body}</main></html>',
        encoding="utf-8",
    )


def tables(path):
    if not path.is_file():
        return {}
    if path.suffix == ".xlsx":
        return pd.read_excel(path, sheet_name=None, dtype=object, keep_default_na=False)
    try:
        return {"CSV": pd.read_csv(path, dtype=object, keep_default_na=False, encoding="utf-8-sig")}
    except UnicodeError:
        return {"CSV": pd.read_csv(path, dtype=object, keep_default_na=False, encoding="iso-8859-1")}


def same_cell(left, right, column):
    if left == right:
        return True
    numeric = column.endswith(("_CHF", "_Bps")) or column in {
        "Qty", "ExecPrice", "MarketVWAP", "Rolling_Split_Notional",
    }
    if numeric:
        try:
            a, b = Decimal(str(left)), Decimal(str(right))
        except InvalidOperation:
            return False
        # Limit serialization tolerance to well below a cent.
        return a.is_finite() and b.is_finite() and abs(a - b) < Decimal("0.000001")
    return isinstance(left, (int, float)) and isinstance(right, (int, float)) and isclose(
        left, right, rel_tol=1e-13, abs_tol=1e-10,
    )


class ReportRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.stack = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.stack.append([])
        elif tag in {"th", "td"}:
            self.text.append([])

    def handle_data(self, data):
        if self.text:
            self.text[-1].append(data)

    def handle_endtag(self, tag):
        if tag in {"th", "td"} and self.text:
            value = " ".join("".join(self.text.pop()).split())
            if self.stack:
                self.stack[-1].append(value)
        elif tag == "tr" and self.stack:
            row = tuple(self.stack.pop())
            if any(row):
                self.rows.append(row)


def report_rows(path):
    encoding = "utf-16" if path.read_bytes()[:2] in {b"\xff\xfe", b"\xfe\xff"} else "utf-8"
    report = ReportRows()
    report.feed(path.read_text(encoding=encoding))
    return report.rows


def display_cell_matches(native, python):
    if native == python or not native and python in {"None", "NaN", "nan"}:
        return True
    try:
        left = Decimal(native.replace(",", ""))
        right = Decimal(python.replace(",", ""))
        return left.is_finite() and right.is_finite() and abs(left - right) <= Decimal("0.5").scaleb(
            min(left.as_tuple().exponent, 0),
        )
    except InvalidOperation:
        return False


def report_matches(left, right):
    if not left.is_file() or not right.is_file():
        return False
    native_rows, python_rows = report_rows(left), report_rows(right)
    # Designer wraps its data table in layout tables. Use the independently
    # rendered headers to locate the corresponding native section.
    if not python_rows or python_rows[0] not in native_rows:
        return False
    begin = native_rows.index(python_rows[0])
    native_rows = native_rows[begin:begin + len(python_rows)]
    return len(native_rows) == len(python_rows) and all(
        len(a) == len(b) and all(display_cell_matches(x, y) for x, y in zip(a, b))
        for a, b in zip(native_rows, python_rows)
    )


def mail_matches(output, filename):
    messages = []
    for folder in ("alteryx_outputs", "python_outputs"):
        path = output / folder / "compliance_alert.eml"
        if not path.is_file():
            return False
        message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
        body = message.get_body(preferencelist=("html", "plain"))
        if body is None:
            return False
        attachments = {part.get_filename(): part.get_payload(decode=True) for part in message.iter_attachments()}
        if filename not in attachments:
            return False
        data = pd.read_csv(BytesIO(attachments[filename]), dtype=object, keep_default_na=False, encoding="utf-8-sig")
        expected = tables(output / folder / filename)["CSV"]
        if not data.equals(expected):
            return False
        messages.append([*(str(message[key]) for key in ("From", "To", "Subject")), body.get_content().strip()])
    return messages[0] == messages[1]


def preview(frame, other):
    if frame is None:
        return "<p>输出缺失</p>"
    header = "".join(f"<th>{escape(str(name))}</th>" for name in frame.columns)
    rows = []
    for index, row in enumerate(frame.head(20).itertuples(index=False, name=None)):
        entries = []
        for column, value in enumerate(row):
            peer = None if other is None or index >= len(other) or column >= len(other.columns) else other.iloc[index, column]
            different = peer is None or not same_cell(value, peer, str(frame.columns[column]))
            style = ' class="different"' if different else ""
            entries.append(f"<td{style}>{escape(str(value))}</td>")
        rows.append("<tr>" + "".join(entries) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def probe_summary(output):
    evidence = output / "phase_one" / "comparison.json"
    if not evidence.is_file():
        return ""
    comparison = json.loads(evidence.read_text(encoding="utf-8"))
    entries = []
    for item in comparison["comparisons"]:
        if item.get("direction") != "outputs" or item["status"] == "match":
            continue
        first = next(iter(item.get("value_differences", [])), {})
        field = first.get("column", "")
        entries.append(
            f'<tr><td>{escape(item["node_id"])}</td><td>{escape(item["anchor"])}</td>'
            f'<td>{escape(item["status"])}</td><td>{escape(str(field))}</td></tr>'
        )
    return ('<details class="sheet"><summary>Phase 1 节点差异</summary>'
            '<p><a href="phase_one/comparison.json">完整探针对比</a></p>'
            '<table><thead><tr><th>节点</th><th>输出</th><th>状态</th><th>首个差异字段</th></tr></thead>'
            f'<tbody>{"".join(entries)}</tbody></table></details>')


def compare(output, filename, report, *, native_status, python_rc, gaps, scenario, metrics, phase_one=None):
    native = tables(output / "alteryx_outputs" / filename)
    python = tables(output / "python_outputs" / filename)
    normalization = ""
    if scenario == TITLES[3]:
        key = "Transaction_Reference_Number"
        for book, folder in ((native, "alteryx_outputs"), (python, "python_outputs")):
            for sheet, frame in book.items():
                if key in frame and "RecordID" in frame:
                    regulatory = frame.drop(columns="RecordID")
                    # Remove the empty template row only. A partially filled
                    # row stays in the report and must match.
                    book[sheet] = regulatory.loc[regulatory.ne("").any(axis=1)].sort_values(
                        key, kind="stable",
                    ).reset_index(drop=True)
                    if len(regulatory.columns) == 87:
                        book[sheet].to_excel(output / folder / "MIFID regulatory fields.xlsx", index=False, sheet_name=sheet)
        normalization = ("<p>87 列监管字段导出按交易参考编号排列，排除全空模板行。"
                         "原始工作簿保留 RecordID 和原有模板行。</p>")
    compared = matched = 0
    equal = bool(native) and native.keys() == python.keys()
    sections = []
    for sheet in dict.fromkeys([*native, *python]):
        left, right = native.get(sheet), python.get(sheet)
        if left is None or right is None or left.shape != right.shape or list(left.columns) != list(right.columns):
            equal = False
        elif left is not None:
            compared += left.size
            matched += sum(
                same_cell(a, b, str(column))
                for column in left.columns for a, b in zip(left[column], right[column], strict=True)
            )
        sections.append(f'<h2>{escape(sheet)}</h2><div class="pair"><div class="sheet">'
                        f'<h3>Designer</h3>{preview(left, right)}</div><div class="sheet">'
                        f'<h3>Python</h3>{preview(right, left)}</div></div>')
    artifact_links = []
    for folder, name in (("alteryx_outputs", "Designer"), ("python_outputs", "Python")):
        files = sorted((output / folder).iterdir())
        artifact_links.append(f"<article><h2>{name}</h2>" + " · ".join(
            f'<a href="{folder}/{escape(file.name, quote=True)}">{escape(file.name)}</a>' for file in files
        ) + (f'<iframe title="{name} HTML" sandbox src="{folder}/{report}"></iframe>'
             if report and (output / folder / report).is_file() else "") + "</article>")
    expected_html = not report or report_matches(output / "alteryx_outputs" / report, output / "python_outputs" / report)
    email_ok = scenario != TITLES[1] or mail_matches(output, filename)
    expected_columns = scenario != TITLES[3] or all(
        len(frame.columns) == 87 for book in (native, python) for frame in book.values()
    )
    complete = (equal and expected_columns and compared > 0 and compared == matched and not python_rc and not gaps
                and native_status == "outputs_ready" and expected_html and email_ok)
    status = "MATCH" if complete else "DIFF" if native and python and not equal or compared != matched else "INCOMPLETE"
    values = [f"Designer {native_status}", f"Python exit {python_rc}", f"匹配单元格 {matched:,} / {compared:,}"]
    if report:
        values.append("HTML 表格一致" if expected_html else "HTML 表格待核对")
    if scenario == TITLES[1]:
        values.append("EML 正文及 CSV 附件一致" if email_ok else "EML 正文或附件待核对")
    if phase_one:
        values.append(f"Phase 1 {phase_one}")
    if equal and list(native) != list(python):
        values.append("工作表按名称核对，页签顺序不同")
    if gaps:
        values.append(f"Phase 2 缺口 {len(gaps)}")
    cards = []
    for label, left, right in metrics(native, python):
        agrees = left == right and left != "—"
        marker = '<strong class="match">MATCH</strong>' if agrees else '<strong class="gap">待核对</strong>'
        cards.append(f'<article><h3>{escape(label)}</h3><p>Designer <b>{escape(str(left))}</b></p>'
                     f'<p>Python <b>{escape(str(right))}</b> · {marker}</p></article>')
    target = output / "comparison.html"
    page(target, scenario,
         '<p><a href="' + ("../../" if scenario == TITLES[1] else "../") + 'index.html">总览</a> · '
         '<a href="pipeline.py">生成的 pipeline.py</a> · <a href="package/cli.py">独立运行入口</a></p>'
         f'<p class="{("match" if complete else "gap")}">{status} · {escape(" · ".join(values))}</p>'
         f'<div class="cards">{"".join(cards)}</div><div class="pair">{"".join(artifact_links)}</div>{normalization}'
         + "".join(sections) + probe_summary(output))
    return status, values


def execute_designer(entry, work, pid):
    write_json(work / "designer-plan.json", [entry])
    script = ROOT.parents[1] / "scripts" / "designer_click_run.ps1"
    command = [
        "pwsh", "-NoProfile", "-File", str(script), "-Plan", str(work / "designer-plan.json"),
        "-Report", str(work / "designer-run.json"),
        "-AppLaunch", "options", "-TimeoutSeconds", "65", "-UseAppDefaults",
    ]
    if pid is not None:
        command += ["-DesignerProcessId", str(pid)]
    with (work / "designer.log").open("w", encoding="utf-8") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=150, check=False)
    outcome = work / "designer-run.json"
    return json.loads(outcome.read_text(encoding="utf-8-sig"))[0]["status"] if outcome.is_file() else "blocked"


def run_designer(workflow, answers, watched, work, pid):
    write_json(workflow.parent / "manifest.json", {
        "instrumented_file": workflow.name, "instrumented_sha256": file_hash(workflow),
        "answers": answers, "macro_dependencies_sha256": {}, "probes": [],
        "sink_files": {"final": watched},
    })
    return execute_designer({"run_dir": str(workflow.parent), "workflow": str(workflow), "status": "ready"}, work, pid)


def run_phase_one(workflow, answers, output, pid, endpoint):
    capture = output / "phase_one"
    # Keep the workbook substitution valid when probe preparation resolves the
    # input to its absolute location.
    if answers and "File Browse (10)" in answers:
        tree = ET.parse(workflow)
        path = answers["File Browse (10)"]
        file = tree.find(".//Node[@ToolID='4']/Properties/Configuration/File")
        file.text = path + "|||" + file.text.partition("|||")[2]
        action = next(item for item in tree.iter("Action") if item.find("ToolId").get("value") == "11")
        action.find("ReplaceText").text = path
        workflow = workflow.parent / "phase-one-source.yxwz"
        tree.write(workflow, encoding="utf-8", xml_declaration=True)
    try:
        name = f"probes-{output.parent.name}-{output.name}{workflow.suffix}"
        manifest = prepare(workflow, capture, answers=answers, instrumented_filename=name,
                           best_effort=True, capture_reference=False)
        source = capture / "phase_one.py"
        source.write_text(PythonGenerator().generate(XmlWorkflowParser().parse(workflow)), encoding="utf-8")

        def loopback(request):
            from alteryx2python.tools.download import _default_transport

            if request["url"] != endpoint:
                raise ValueError("The benchmark transport only accepts the OMR fixture URL")
            return _default_transport(request)

        python = capture_python(
            workflow, output_directory=capture / "python-outputs", answers=answers,
            generated_entry=runpy.run_path(str(source))["run_with_context"],
            runtime_config=({"delivery_profile": "html-draft-v1", "output_dir": str(capture / "python-outputs")}
                            if endpoint is None else {"download_transport": loopback}),
        )
        write_json(capture / "python.json", python)
        status = execute_designer({"run_dir": str(capture), "workflow": str(capture / name), "status": "ready"}, capture, pid)
        if manifest["engine_mode"] == "amp" and any((capture / probe["file"]).is_file() for probe in manifest["probes"]):
            entry = prepare_amp_export(capture)
            execute_designer(entry, Path(entry["run_dir"]), pid)
        if status not in {"outputs_ready", "completed_missing_outputs", "output_timeout"}:
            return status
        attest_native(capture, "success", reviewer="Designer automation", allow_incomplete=True)
        native = collect_native(capture, manual=True)
        result = compare_runs(native, python)
        write_json(capture / "comparison.json", result)
        matches = sum(item["status"] == "match" and item["direction"] == "outputs" for item in result["comparisons"])
        return f'{result["status"]} ({matches}/{len(manifest["probes"])} 输出探针)'
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        capture.mkdir(exist_ok=True)
        (capture / "error.log").write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        return "incomplete"


def write_mail_preview(directory, mime):
    (directory / "compliance_alert.eml").write_bytes(mime)
    message = BytesParser(policy=policy.default).parsebytes(mime)
    body = message.get_body(preferencelist=("html",))
    if body:
        (directory / "compliance_alert_body.html").write_text(body.get_content(), encoding="utf-8")


def omr_server(responses):
    def omr(request):
        data = json.loads(request["body"])
        key = str(data["tradeId"])
        return HttpResponse(body=json.dumps(responses[key]).encode(), headers={"Content-Type": "application/json"})

    return LocalHttpTestServer({("POST", "/omr"): omr})


def package_cli(package, inputs, outputs, config=None):
    command = [sys.executable, str(package / "cli.py"), "--input-dir", str(inputs),
               "--output-dir", str(outputs), "--log-level", "OFF"]
    if config:
        command += ["--config", str(config)]
    return command


def replay_python(case, output):
    """Replay an exported package with fresh outputs and a fresh OMR port."""
    output.mkdir(parents=True, exist_ok=False)
    overrides = case / "workbooks.json"
    config = json.loads(overrides.read_text(encoding="utf-8")) if overrides.is_file() else {}
    inputs = case / "inputs"
    fixture = inputs / "omr_responses.json"
    with ExitStack() as stack:
        if fixture.is_file():
            responses = json.loads(fixture.read_text(encoding="utf-8"))
            http = stack.enter_context(omr_server(responses))
            config["parameters"] = {
                "user_omr_url": http.url + "/omr",
                "file_browse_10": str(inputs / "ROB-102928 Input template - EQ.xlsx"),
            }
        override = output / "replay_config.json"
        write_json(override, config)
        return subprocess.run(package_cli(case / "package", inputs, output, override), timeout=120, check=False).returncode


def kpis(index, responses):
    def stats(left, right):
        if index == 0:
            sheet = "Desk_PnL_Summary"
            for field in ("Executions", "Net_Settlement_CHF", "Realized_PnL_CHF"):
                yield (field, *(round(book[sheet][field].astype(float).sum(), 2)
                                if sheet in book and field in book[sheet] else "—" for book in (left, right)))
            yield ("Recon Breaks", *(len(book["Recon_Breaks"]) if "Recon_Breaks" in book else "—"
                                     for book in (left, right)))
        else:
            yield ("输出行数 × 列数", *(" × ".join(map(str, next(iter(book.values())).shape)) if book else "—"
                                        for book in (left, right)))
            if index == 1:
                for field in ("HIGH", "MEDIUM"):
                    yield (f"{field} 告警", *(int(book["CSV"]["Risk_Level"].eq(field).sum()) if "CSV" in book else "—"
                                             for book in (left, right)))
            if index == 2:
                for field in ("Market_Value_CHF", "VaR_99_1D_CHF"):
                    yield (field, *(round(book["Positions"][field].astype(float).sum(), 2)
                                    if "Positions" in book else "—" for book in (left, right)))
            if index == 3:
                yield ("输入交易与 OMR POST", *responses)
    return stats


def run_case(output, index, pid, threshold, *, phase_one=False):
    scenario = TITLES[index]
    inputs = output / "inputs"
    inputs.mkdir(parents=True, exist_ok=False)
    native = output / "alteryx_outputs"
    native.mkdir()
    python = output / "python_outputs"
    python.mkdir()
    watched = WORKBOOKS[index]
    answers = None
    native_answers = None
    with ExitStack() as stack:
        smtp = stack.enter_context(LocalSmtpCaptureServer()) if index == 1 else None
        http = None
        if index == 3:
            responses = {}
            http = stack.enter_context(omr_server(responses))
            mifid(inputs, http.url + "/omr")
            responses.update(json.loads((inputs / "omr_responses.json").read_text(encoding="utf-8")))
            input_file = "ROB-102928 Input template - EQ.xlsx"
            answers = {"File Browse (10)": str(inputs / input_file), "Text Box (57)": "ubs-local"}
            native_answers = {**answers, "File Browse (10)": str(native / input_file)}
        elif index == 1:
            desk = "ALL" if threshold == 2000000 else "APAC_EQ"
            surveillance(inputs, threshold=threshold, desk=desk)
        else:
            (equities if index == 0 else positions)(inputs)
        workflow = next(inputs.glob("*.yx*"))
        if smtp:
            root = ET.parse(workflow)
            root.find(".//Configuration/Port").text = str(smtp.port)
            email = root.find(".//Configuration/SMTPServerName/..")
            attachment = ET.SubElement(ET.SubElement(email, "Attachments"), "Attachment")
            ET.SubElement(attachment, "Value").text = watched
            ET.SubElement(attachment, "ValueIsField").text = "False"
            root.write(workflow, encoding="utf-8", xml_declaration=True)
            answers = native_answers = {"threshold": threshold, "trade_date": "2026-11-27", "desk": desk}
        for entry in inputs.iterdir():
            shutil.copy2(entry, native / entry.name)
        native_workflow = native / (workflow.stem + "-" + output.name + workflow.suffix)
        (native / workflow.name).rename(native_workflow)
        try:
            native_status = run_designer(native_workflow, native_answers, watched, output, pid)
        except subprocess.TimeoutExpired:
            native_status = "timeout"
        before_requests = len(http.requests) if http else 0
        if smtp and smtp.messages:
            write_mail_preview(native, smtp.messages[0]["mime"])
        # Retain the executed canvas under inputs and keep the output panel focused on results.
        shutil.move(native_workflow, inputs / native_workflow.name)
        shutil.move(native / "manifest.json", output / "designer-manifest.json")
        for entry in inputs.iterdir():
            clone = native / entry.name
            if clone.is_file():
                clone.unlink()
        compiler = ModularPackageGenerator()
        gaps = []
        python_rc = 1
        try:
            phase_one_source = output / "phase_one.py"
            phase_one_source.write_text(PythonGenerator().generate(XmlWorkflowParser().parse(workflow)), encoding="utf-8")
            package = compiler.generate(read_phase_one(phase_one_source), answers=answers,
                                        delivery_profile="html-draft-v1" if index != 3 else None)
            package.write(output / "package")
            shutil.copy2(output / "package" / "pipeline.py", output / "pipeline.py")
            gaps = package.manifest.get("migration_gaps", [])
            overrides = None
            # Sheet-replacement sinks share the configured workbook in this benchmark.
            workbook_overrides = {
                key: {"isolated_filename": meta["filename"]}
                for key, meta in package.config_spec.outputs.items() if meta.get("replace_sheet")
            }
            if index == 2:
                order = ("Risk_Buckets", "Positions")
                for key, override in workbook_overrides.items():
                    override["sheet_index"] = order.index(package.config_spec.outputs[key]["sheet_name"])
            if workbook_overrides:
                overrides = output / "workbooks.json"
                write_json(overrides, {"outputs": workbook_overrides})
            with (output / "python.log").open("w", encoding="utf-8") as log:
                python_rc = subprocess.run(package_cli(output / "package", inputs, python, overrides),
                                           stdout=log, stderr=subprocess.STDOUT, timeout=120, check=False).returncode
            if smtp:
                draft = next(python.glob("*.eml"), None)
                if draft:
                    write_mail_preview(python, draft.read_bytes())
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            (output / "python.log").write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        responses_seen = (before_requests, len(http.requests) - before_requests) if http else (0, 0)
        phase_one_status = run_phase_one(workflow, answers, output, pid, http.url + "/omr" if http else None) if phase_one else None
        return compare(output, watched, REPORTS[index], native_status=native_status, python_rc=python_rc, gaps=gaps,
                       scenario=scenario, metrics=kpis(index, responses_seen), phase_one=phase_one_status)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--designer-pid", type=int)
    parser.add_argument("--scenario", type=int, choices=range(1, 5), action="append")
    parser.add_argument("--skip-phase-one", action="store_true")
    parser.add_argument("--replay-python", type=Path, metavar="CASE_DIRECTORY")
    args = parser.parse_args()
    root = args.output_dir.resolve()
    if args.replay_python:
        return replay_python(args.replay_python.resolve(), root)
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for index in (number - 1 for number in (args.scenario or range(1, 5))):
        destination = root / SCENARIOS[index]
        cases = [("default", 2000000), ("tight_threshold", 500000)] if index == 1 else [(None, None)]
        for label, threshold in cases:
            output = destination / label if label else destination
            status, details = run_case(output, index, args.designer_pid, threshold, phase_one=not args.skip_phase_one)
            entries.append((output.relative_to(root).as_posix(), TITLES[index] + (f" · {label}" if label else ""),
                            status, details))
            print(entries[-1], flush=True)
            write_index(root, entries)
    return int(any(
        state != "MATCH" or any(item.startswith("Phase 1 ") and not item.startswith("Phase 1 match (")
                               for item in details)
        for _, _, state, details in entries
    ))


def write_index(root, entries):
    page(root / "index.html", "UBS 金融交易与监管报表基准",
         '<p><a href="SUMMARY.md">验收摘要</a></p><div class="cards">' + "".join(
             f'<article><h2><a href="{path}/comparison.html">{title}</a></h2>'
             f'<p><strong>{state}</strong> · {escape(" · ".join(description))}</p>'
             f'<p><a href="{path}/package/pipeline.py">Python 源码</a> · '
             f'<a href="{path}/package/cli.py">独立运行入口</a></p></article>'
             for path, title, state, description in entries
         ) + "</div>")
    (root / "SUMMARY.md").write_text(
        "# UBS 金融交易与监管报表基准\n\n"
        "每项首个状态来自业务文件核对。Phase 1 显示单独的逐节点探针对比。\n\n"
        + "\n".join(f"- **{state}** [{title}]({path}/comparison.html) · {' · '.join(description)}"
                     for path, title, state, description in entries)
        + "\n", encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
