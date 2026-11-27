"""Run the strict test path for explicit, replayable tabular configuration cases."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import mkdtemp
from xml.etree import ElementTree as ET

from alteryx2python.generator.package_compiler import ModularPackageGenerator
from alteryx2python.parser.xml_parser import XmlWorkflowParser

from .archetype_datasets import build_archetype, derive_universal_perturbations
from .canvas_packer import CanvasCase, pack_tool_configurations
from .runner import comparable_artifact, capture_python, file_hash, prepare, read_yxdb, verify_manifest, write_json
from .schema_registry import AMP_SENSITIVE
from .sensitivity import verify_config_sensitivity
from .snapshot import compare_snapshots, frame_snapshot


def _configuration_values(xml: str) -> dict:
    values = {}

    def visit(element, path):
        values.setdefault(path, []).append((element.text or "").strip())
        for name, value in element.attrib.items():
            values.setdefault(f"{path}/@{name}", []).append(value)
        for child in element:
            visit(child, f"{path}/{child.tag}")

    root = ET.fromstring(xml)
    visit(root, root.tag)
    return values


def check_tool(
    tool_type: str, definition: Path, work_dir: Path, *, data_runs: Path | None = None,
) -> dict:
    definition = definition.resolve()
    data = json.loads(definition.read_text(encoding="utf-8-sig"))
    if data["tool_type"] != tool_type:
        raise ValueError("Fixture tool does not match the requested tool")
    cases = [
        CanvasCase(row["case_id"], row["configuration_xml"], tuple(map(tuple, row.get("inputs", [("input", "Input")]))))
        for row in data["cases"]
    ]
    if len(cases) < 2:
        raise ValueError("At least one configuration flip is required")
    pairs = data["sensitivity_pairs"]
    ids = {case.case_id for case in cases}
    if {case_id for pair in pairs for case_id in pair} != ids or any(
        len(pair) != 2 or pair[0] == pair[1] for pair in pairs
    ):
        raise ValueError("Every case must belong to a baseline/variant sensitivity pair")
    configs = {case.case_id: _configuration_values(case.configuration_xml) for case in cases}
    inputs = {case.case_id: case.inputs for case in cases}
    axes = {case["case_id"]: case["axis"] for case in data["cases"]}
    for baseline, variant in pairs:
        left, right = configs[baseline], configs[variant]
        changed = {path for path in left.keys() | right.keys() if left.get(path) != right.get(path)}
        if changed != {axes[variant]} or inputs[baseline] != inputs[variant]:
            raise ValueError(f"Configuration pair {baseline}/{variant} must vary only {axes[variant]}")

    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=False)
    bundle = build_archetype(data["dataset_id"], work_dir / "data")
    datasets = {"base": bundle, **derive_universal_perturbations(bundle)}
    if data_runs is not None:
        _attach_typed_inputs(data_runs.resolve(strict=True), datasets)
    engines = ("amp",) if tool_type == "ControlContainer" else (
        ("classic", "amp") if tool_type in AMP_SENSITIVE else ("classic",)
    )
    checks = []
    expected_failures = {}
    negative_error = data.get("negative_schema_failure")
    for engine in engines:
        for label, dataset in datasets.items():
            artifact = pack_tool_configurations(
                tool_type, cases, dataset,
                workflow_path=work_dir / "workflows" / f"{engine}-{label}.yxmd",
                amp=engine == "amp",
            )
            source = artifact.workflow
            check_directory = work_dir / "checks" / source.stem
            # Native preparation rejects workflows that need external execution adapters.
            manifest = prepare(source, check_directory / "native", capture_reference=False)
            workflow = XmlWorkflowParser().parse(source)
            package = ModularPackageGenerator().generate(workflow)
            mapped = {row["source_tool_id"] for row in package.manifest["nodes"]}
            if not set(artifact.case_nodes.values()) <= mapped:
                raise ValueError(f"Phase 2 did not account for all case nodes in {source.name}")
            run = capture_python(source, output_directory=check_directory / "phase-one")
            write_json(check_directory / "phase-one.json", run)
            expected_status = "success"
            if label == "P_NEGATIVE_SCHEMA" and negative_error:
                expected_status = "failed"
                expected_failures[source.name] = {
                    "message": negative_error["message"],
                    "failed_nodes": [artifact.case_nodes[case_id] for case_id in negative_error["failed_cases"]],
                }
            if run["status"] != expected_status:
                raise ValueError(f"{source.name} Phase 1 {run['status']}: {run['failure']}")

            sensitivity_results = []
            if label == "base":
                case_outputs = {}
                for case, node in artifact.case_nodes.items():
                    case_output = dict(run["nodes"][node])
                    if node in run["sink_artifacts"]:
                        sink = next((check_directory / "phase-one").glob(f"python-sink-*-{node}.*"))
                        case_output["artifacts"] = {"file": comparable_artifact(sink)}
                    case_outputs[case] = case_output
                for baseline, variant in pairs:
                    result = verify_config_sensitivity(
                        tool_type, case_outputs[baseline], case_outputs[variant], data["dataset_id"],
                    )
                    sensitivity_results.append({"baseline": baseline, "variant": variant, **asdict(result)})
            checks.append({
                "workflow": str(source), "source_sha256": manifest["source_sha256"],
                "inputs_sha256": manifest["inputs_sha256"], "engine": engine,
                "dataset": label, "case_nodes": artifact.case_nodes,
                "phase_two_sha256": package.manifest["generated_sha256"],
                "sensitivity": sensitivity_results,
                "expected_status": expected_status,
            })
    result = {
        "status": "checked", "tool_type": tool_type, "checks": checks,
        "fixture_definition": str(definition), "fixture_sha256": file_hash(definition),
    }
    if expected_failures:
        write_json(work_dir / "expected-failures.json", expected_failures)
    write_json(work_dir / "check-tool.json", result)
    return result


def _attach_typed_inputs(directory: Path, datasets: dict) -> None:
    """Reuse a recorded Classic source table when CSV transport changes its values."""
    runs = {}
    for folder in sorted(directory.iterdir()):
        if (folder / "manifest.json").is_file():
            manifest = verify_manifest(folder)
            runs[Path(manifest["source"]).stem] = (folder, manifest)
    for label, dataset in datasets.items():
        if set(dataset.tables) != {"input"} or f"classic-{label}" not in runs:
            raise ValueError(f"Expected one typed source table for {label}")
        folder, manifest = runs[f"classic-{label}"]
        source_ids = {node["node_id"] for node in manifest["nodes"] if node["tool_type"] == "DbFileInput"}
        probes = [probe for probe in manifest["probes"] if probe["node_id"] in source_ids and probe["anchor"] == "Output"]
        if len(probes) != 1 or manifest["engine_mode"] == "amp":
            raise ValueError(f"Expected a single Classic Input Data probe for {label}")
        typed_path = folder / probes[0]["file"]
        if compare_snapshots(frame_snapshot(dataset.tables["input"]), read_yxdb(typed_path))["status"] != "match":
            raise ValueError(f"Typed input does not match the generated dataset for {label}: {typed_path}")
        destination = dataset.directory / "input.yxdb"
        shutil.copyfile(typed_path, destination)
        dataset.files["input"] = destination


def verify_tool(
    tool_type: str, work_dir: Path, designer_pid: int | None,
    *, timeout: int = 60, native_directory: Path | None = None,
) -> dict:
    work_dir = work_dir.resolve()
    checked = json.loads((work_dir / "check-tool.json").read_text(encoding="utf-8"))
    if checked["status"] != "checked" or checked["tool_type"] != tool_type or not checked["checks"]:
        raise ValueError("Run check-tool for this tool before native verification")
    for check in checked["checks"]:
        paths = {check["workflow"]: check["source_sha256"], **check["inputs_sha256"]}
        for path, digest in paths.items():
            if file_hash(Path(path)) != digest:
                raise ValueError(f"Scaffold input or workflow changed after checking: {path}")
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    attempts = work_dir / "designer-attempts"
    attempts.mkdir(exist_ok=True)
    attempt = Path(mkdtemp(dir=attempts)) / "evidence"
    delivery = attempt / "delivery"
    if native_directory is None:
        shell = shutil.which("pwsh")
        script = scripts / "run_designer_parity.ps1"
        if not shell or not script.is_file() or designer_pid is None:
            raise ValueError("Designer automation needs PowerShell 7 and a Designer process ID")
        native_directory = attempt / "native"
        command = [
            shell, "-NoProfile", "-File", str(script), "-Source", str(work_dir / "workflows"),
            "-Output", str(attempt), "-DesignerProcessId", str(designer_pid),
            "-TimeoutSeconds", str(timeout),
        ]
        if (work_dir / "expected-failures.json").is_file():
            command.extend(("-ExpectedFailures", str(work_dir / "expected-failures.json")))
    else:
        native_directory = native_directory.resolve(strict=True)
        command = [
            sys.executable, str(scripts / "parity_batch.py"), "verify-delivery", str(native_directory),
            "--output-dir", str(delivery), "--jobs", "2",
        ]
    env = {**os.environ, "ALTERYX2PYTHON_PYTHON": sys.executable}
    process = subprocess.run(command, capture_output=True, check=False, env=env)
    (work_dir / "designer.stdout.txt").write_bytes(process.stdout)
    (work_dir / "designer.stderr.txt").write_bytes(process.stderr)
    summary = delivery / "summary.json"
    rows = json.loads(summary.read_text(encoding="utf-8-sig")) if summary.is_file() else []
    expected = {row["workflow"]: row for row in checked["checks"]}
    present = {row.get("source"): row for row in rows if row.get("source")}
    passed = (
        process.returncode == 0 and expected.keys() == present.keys()
        and all(
            present[path]["status"] == "match"
            and present[path]["phase_two_sha256"] == check["phase_two_sha256"]
            and not present[path].get("migration_gaps")
            for path, check in expected.items()
        )
    )
    result = {
        "status": "match" if passed else "incomplete", "tool_type": tool_type,
        "expected_workflows": len(expected), "matched_workflows": sum(row["status"] == "match" for row in rows),
        "designer_returncode": process.returncode, "summary": str(summary),
        "native_directory": str(native_directory),
        "checks_sha256": file_hash(work_dir / "check-tool.json"),
        "evidence": _receipt_files(native_directory, delivery, rows) if passed else {},
    }
    write_json(work_dir / "verify-tool.json", result)
    return result


def _receipt_files(native_directory: Path, output: Path, rows: list[dict]) -> dict[str, str]:
    paths = [output / "summary.json"]
    for row in rows:
        run = native_directory / row["run"]
        delivery = output / row["run"]
        review = json.loads((run / "manual-review.json").read_text(encoding="utf-8"))
        paths.extend(run / name for name in ("manifest.json", "manual-review.json"))
        paths.extend(run / filename for filename in review["output_sha256"])
        paths.extend(delivery / name for name in (
            "acceptance.json", "native-vs-phase-one.json", "phase-one-vs-phase-two.json",
            "phase-one-capture.json", "phase_one.py", "package/manifest.json", "package/pipeline.py",
        ))
        package = delivery / "package"
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        paths.extend(package / filename for filename in manifest["file_sha256"])
    return {str(path): file_hash(path) for path in paths}
