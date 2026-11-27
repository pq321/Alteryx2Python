import csv
import json
from pathlib import Path

import pytest

from alteryx2python.parity.ledger import COLUMNS, _verify_receipt
from alteryx2python.parity.runner import file_hash
from alteryx2python.parity.scope import PALETTE_SCOPE


COVERAGE = Path(__file__).resolve().parents[1] / "docs" / "coverage"


def test_ledger_has_every_schema_and_never_claims_a_pass_without_a_receipt():
    expected = {tool for kinds in PALETTE_SCOPE.values() for tool in kinds.split()}
    assert {path.stem for path in (COVERAGE / "schemas").glob("*.json")} == expected
    with (COVERAGE / "tool_configuration_matrix.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames) == COLUMNS
        rows = {row["case_id"]: row for row in reader}
    assert expected <= {row["tool_type"] for row in rows.values()}
    for row in rows.values():
        if row["overall_status"] == "VERIFIED":
            receipt = Path(row["receipt_path"])
            assert row["receipt_sha256"] == file_hash(receipt)
            cases, engines = _verify_receipt(receipt, rows)
            assert row["case_id"] in cases
            assert row["gate1_schema_mapped"] == row["gate2_config_flip"] == row["gate4_phase2_native"] == "PASS"
            assert row["gate3_designer_classic"] == ("PASS" if "classic" in engines else "N/A")
            assert row["gate3_designer_amp"] == ("PASS" if "amp" in engines else "N/A")


def test_receipt_hash_prevents_reusing_edited_check_results(tmp_path):
    checks = tmp_path / "check-tool.json"
    checks.write_text('{"status":"checked"}', encoding="utf-8")
    receipt = tmp_path / "verify-tool.json"
    receipt.write_text(json.dumps({"status": "match", "checks_sha256": file_hash(checks)}), encoding="utf-8")
    checks.write_text('{"status":"checked","checks":[]}', encoding="utf-8")
    with pytest.raises(ValueError, match="check report changed"):
        _verify_receipt(receipt, {})
