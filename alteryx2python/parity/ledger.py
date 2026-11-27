"""Generate the coverage ledger from definitions and reproducible evidence."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

from .schema_registry import AMP_SENSITIVE
from .scope import PALETTE_SCOPE, WORKFLOW_FEATURES
from .runner import file_hash

FIXTURES = Path("tests/fixtures/tool_matrix")
DATASETS = frozenset({"base", "P_EMPTY_0ROW", "P_SINGLE_1ROW", "P_ALL_NULL_COL", "P_NEGATIVE_SCHEMA"})


COLUMNS = (
    "case_id", "priority", "category", "tool_type", "designer_name", "engine_tier",
    "config_axis", "xml_path", "option_scenario", "user_input_state", "support_policy",
    "dataset_id", "sample_usage_ref", "gate1_schema_mapped", "gate2_config_flip",
    "gate3_designer_classic", "gate3_designer_amp", "gate4_phase2_native",
    "overall_status", "fixture_workflow", "receipt_path", "receipt_sha256",
)


def _write_csv(path: Path, columns, rows) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    temp = path.with_suffix(".csv.tmp")
    temp.write_text(stream.getvalue(), encoding="utf-8", newline="")
    temp.replace(path)


def _definition(case_id, tool, category, axis, scenario, **fields):
    tier = "amp_only" if tool == "ControlContainer" else "classic_and_amp" if tool in AMP_SENSITIVE else "classic_primary"
    return {
        **dict.fromkeys(COLUMNS, ""),
        "case_id": case_id, "priority": "P1", "category": category,
        "tool_type": tool, "designer_name": tool, "engine_tier": tier,
        "config_axis": axis, "option_scenario": scenario, "support_policy": "supported",
        "user_input_state": "static", "gate1_schema_mapped": "PENDING",
        "gate3_designer_classic": "N/A" if tier == "amp_only" else "UNVERIFIED",
        "gate3_designer_amp": "N/A" if tier == "classic_primary" else "UNVERIFIED",
        "gate4_phase2_native": "UNVERIFIED", "overall_status": "IN_PROGRESS",
        **fields,
    }


def _schema_rows(directory: Path, kinds: dict[str, str]):
    for tool, category in sorted(kinds.items()):
        path = directory / f"{tool}.json"
        if not path.is_file():
            raise ValueError(f"Missing tool schema: {path}")
        schema = json.loads(path.read_text(encoding="utf-8"))
        if schema["tool_type"] != tool:
            raise ValueError(f"Schema does not describe {tool}: {path}")
        for axis, values in sorted(schema["axes"].items()):
            for value in values["declared"]:
                digest = hashlib.sha256(f"{axis}\0{value}".encode()).hexdigest()[:16]
                yield _definition(f"{tool}-{digest}", tool, category, axis, value, xml_path=axis)
        for index, finding in enumerate(schema["unresolved"], 1):
            yield _definition(f"{tool}-schema-gap-{index}", tool, category, "Configuration inventory", finding)


def sync_ledger_from_schemas(directory: Path, *, historical_csv: str = "") -> dict:
    kinds = {kind: category for category, tools in PALETTE_SCOPE.items() for kind in tools.split()}
    rows = {row["case_id"]: row for row in _schema_rows(directory / "schemas", kinds)}
    historical_count = 0
    for row in csv.DictReader(io.StringIO(historical_csv.lstrip("\ufeff"))):
        tool = row["Internal Type"]
        if tool not in kinds and tool not in WORKFLOW_FEATURES:
            continue
        case_id = row["Case ID"]
        if case_id in rows:
            raise ValueError(f"Duplicate coverage case ID: {case_id}")
        rows[case_id] = _definition(
            case_id, tool, kinds.get(tool, "WorkflowFeatures"), row["Configuration"], row["Option or Test Scenario"],
            priority=row["Priority"], designer_name=row["Designer Tool"],
            sample_usage_ref=row["Installed Designer Sample (Candidate)"],
        )
        historical_count += 1
    for feature in set(WORKFLOW_FEATURES) - {row["tool_type"] for row in rows.values()}:
        case_id = f"WorkflowFeatures-{feature}"
        rows[case_id] = _definition(case_id, feature, "WorkflowFeatures", "Feature", feature)
    for path in sorted(FIXTURES.glob("*/*.json")):
        fixture = _read_json(path)
        tool = fixture["tool_type"]
        for case in fixture["cases"]:
            case_id = case["case_id"]
            if case_id in rows:
                raise ValueError(f"Duplicate coverage case ID: {case_id}")
            rows[case_id] = _definition(
                case_id, tool, kinds[tool], case["axis"], case["scenario"],
                xml_path=case["axis"], dataset_id=fixture["dataset_id"],
                fixture_workflow=path.as_posix(),
            )

    result = _write_ledgers(directory, rows, kinds)
    return {**result, "historical_definitions": historical_count}


def _write_ledgers(directory, rows, kinds) -> dict:
    _write_csv(directory / "tool_configuration_matrix.csv", COLUMNS, (rows[key] for key in sorted(rows)))
    by_tool = {tool: [] for tool in kinds}
    for row in rows.values():
        if row["tool_type"] in by_tool:
            by_tool[row["tool_type"]].append(row)
    summary = []
    for tool, entries in sorted(by_tool.items()):
        status = Counter(row["overall_status"] for row in entries)
        supported = len(entries) - status["OUT_OF_SCOPE"]
        summary.append({
            "tool_type": tool, "total": len(entries), "supported": supported,
            "gate2_pass": sum(row["gate2_config_flip"] == "PASS" for row in entries),
            "gate3_pass": sum(row["gate3_designer_classic"] in {"PASS", "N/A"}
                              and row["gate3_designer_amp"] in {"PASS", "N/A"} for row in entries),
            "gate4_pass": sum(row["gate4_phase2_native"] == "PASS" for row in entries),
            "verified": status["VERIFIED"],
            "completion_percent": f"{100 * status['VERIFIED'] / supported:.2f}" if supported else "",
            "pending_case_ids": " ".join(sorted(row["case_id"] for row in entries if row["overall_status"] == "IN_PROGRESS")),
        })
    _write_csv(directory / "tool_coverage_summary_95.csv", summary[0].keys(), summary)
    return {"tools": len(summary), "cases": len(rows),
            "verified": sum(row["overall_status"] == "VERIFIED" for row in rows.values())}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _verify_receipt(receipt: Path, rows: dict[str, dict]) -> tuple[set[str], set[str]]:
    record = _read_json(receipt)
    if record.get("status") != "match":
        return set(), set()
    checks_file = receipt.with_name("check-tool.json")
    if file_hash(checks_file) != record["checks_sha256"]:
        raise ValueError(f"Scaffold check report changed: {checks_file}")
    evidence = {Path(path).resolve(): digest for path, digest in record["evidence"].items()}

    def attested_json(path):
        path = Path(path).resolve()
        if evidence.get(path) != file_hash(path):
            raise ValueError(f"Missing or changed coverage evidence: {path}")
        return _read_json(path)

    checked = _read_json(checks_file)
    checks = checked["checks"]
    fixture = Path(checked["fixture_definition"]).resolve()
    if not fixture.is_relative_to(FIXTURES.resolve()) or file_hash(fixture) != checked["fixture_sha256"]:
        raise ValueError(f"Coverage fixture changed or is not registered: {fixture}")
    definition = _read_json(fixture)
    case_ids = {case["case_id"] for case in definition["cases"]}
    tool = record["tool_type"]
    if checked["tool_type"] != tool or definition["tool_type"] != tool:
        raise ValueError(f"Tool identities do not agree: {receipt}")
    if not case_ids or any(
        case_id not in rows or rows[case_id]["tool_type"] != tool
        or Path(rows[case_id]["fixture_workflow"]).resolve() != fixture
        for case_id in case_ids
    ):
        raise ValueError(f"Receipt refers to undefined cases: {receipt}")
    tier = next(iter(rows[case_id]["engine_tier"] for case_id in case_ids))
    engines = {"amp"} if tier == "amp_only" else {"classic", "amp"} if tier == "classic_and_amp" else {"classic"}
    matrix = {(check["engine"], check["dataset"]) for check in checks}
    if matrix != {(engine, dataset) for engine in engines for dataset in DATASETS} or len(checks) != len(matrix):
        raise ValueError(f"Incomplete engine or dataset matrix: {receipt}")
    summary_path = Path(record["summary"]).resolve()
    summary = attested_json(summary_path)
    outcomes = {row["source"]: row for row in summary}
    if outcomes.keys() != {check["workflow"] for check in checks} or len(outcomes) != len(summary):
        raise ValueError(f"Designer results do not cover all checked canvases: {receipt}")
    for path, digest in evidence.items():
        if file_hash(path) != digest:
            raise ValueError(f"Evidence hash changed: {path}")
    for check in checks:
        source = Path(check["workflow"])
        if file_hash(source) != check["source_sha256"]:
            raise ValueError(f"Workflow changed after verification: {source}")
        if any(file_hash(Path(path)) != digest for path, digest in check["inputs_sha256"].items()):
            raise ValueError(f"Fixture input changed after verification: {source}")
        if set(check["case_nodes"]) != case_ids:
            raise ValueError(f"Incomplete case matrix: {source}")
        if check["dataset"] == "base":
            flips = check["sensitivity"]
            if ({flip[key] for flip in flips for key in ("baseline", "variant")} != case_ids
                or any(not any(flip[key] for key in ("changed_anchors", "changed_artifacts", "outcome_changed")) for flip in flips)):
                raise ValueError(f"Missing sensitivity results: {source}")
        outcome = outcomes[str(source)]
        delivery = summary_path.parent / outcome["run"]
        native_root = Path(record.get("native_directory") or summary_path.parent.parent / "native").resolve()
        native_dir = native_root / outcome["run"]
        manifest = attested_json(native_dir / "manifest.json")
        review = attested_json(native_dir / "manual-review.json")
        if (
            manifest["source_sha256"] != check["source_sha256"]
            or review["source_sha256"] != manifest["source_sha256"]
            or review["instrumented_sha256"] != manifest["instrumented_sha256"]
            or ("amp" if manifest["engine_mode"] == "amp" else "classic") != check["engine"]
            or review["status"] not in {"success", "failed"}
            or not review["output_sha256"]
            or any(evidence.get(native_dir / name) != digest for name, digest in review["output_sha256"].items())
        ):
            raise ValueError(f"Native attestation does not match this workflow: {source}")
        acceptance = attested_json(delivery / "acceptance.json")
        native = attested_json(delivery / "native-vs-phase-one.json")
        phase_two = attested_json(delivery / "phase-one-vs-phase-two.json")
        package = attested_json(delivery / "package" / "manifest.json")
        if (
            acceptance["source_sha256"] != check["source_sha256"]
            or any(row["status"] != "match" for row in (acceptance, native, phase_two))
            or package.get("migration_gaps")
            or package["generated_sha256"] != check["phase_two_sha256"]
            or package["generated_sha256"] != evidence.get(delivery / "package" / "pipeline.py")
            or acceptance["phase_one_sha256"] != evidence.get(delivery / "phase_one.py")
            or any(evidence.get(delivery / "package" / name) != digest for name, digest in package["file_sha256"].items())
        ):
            raise ValueError(f"Coverage gates did not pass: {source}")
    return case_ids, engines


def attest_ledger_from_receipts(directory: Path, receipt_dirs: list[Path]) -> dict:
    kinds = {kind: category for category, tools in PALETTE_SCOPE.items() for kind in tools.split()}
    with (directory / "tool_configuration_matrix.csv").open(encoding="utf-8", newline="") as stream:
        rows = {row["case_id"]: row for row in csv.DictReader(stream)}
    receipts = sorted({receipt.resolve() for folder in receipt_dirs for receipt in folder.rglob("verify-tool.json")})
    failures = {}
    for receipt in receipts:
        try:
            case_ids, engines = _verify_receipt(receipt, rows)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            failures[str(receipt)] = str(exc)
            continue
        for case_id in case_ids:
            row = rows[case_id]
            row.update(
                gate1_schema_mapped="PASS", gate2_config_flip="PASS",
                gate3_designer_classic="PASS" if "classic" in engines else "N/A",
                gate3_designer_amp="PASS" if "amp" in engines else "N/A",
                gate4_phase2_native="PASS", overall_status="VERIFIED",
                receipt_path=receipt.as_posix(), receipt_sha256=file_hash(receipt),
            )
    if failures:
        return {"status": "invalid_receipts", "failures": failures}
    for row in rows.values():
        if row["overall_status"] == "VERIFIED" and Path(row["receipt_path"]) not in receipts:
            raise ValueError(f"Missing receipt for previously verified case: {row['case_id']}")
    return {"status": "updated", **_write_ledgers(directory, rows, kinds)}
