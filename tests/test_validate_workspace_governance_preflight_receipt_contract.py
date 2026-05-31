"""Purpose: verify workspace governance preflight receipt contract validation.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.validate_workspace_governance_preflight_receipt_contract.
Invariants:
  - The schema artifact carries all required receipt and check fields.
  - Synthetic receipts are accepted without subprocess execution.
  - Contradictory status and return-code evidence is rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import validate_workspace_governance_preflight_receipt_contract as validator


def test_current_receipt_contract_passes() -> None:
    errors = validator.validate_contract()

    assert errors == []
    assert validator.DEFAULT_SCHEMA_PATH.exists()
    assert validator.DEFAULT_SCHEMA_PATH.name == "workspace_governance_preflight_receipt.schema.json"


def test_sample_receipts_have_expected_statuses() -> None:
    passed_receipt, failed_receipt = validator.build_sample_receipts()

    assert passed_receipt["status"] == "passed"
    assert failed_receipt["status"] == "failed"
    assert passed_receipt["terminal_closure_required"] is True
    assert failed_receipt["receipt_is_not_terminal_closure"] is True


def test_invalid_receipt_status_and_check_flag_are_reported() -> None:
    passed_receipt, _failed_receipt = validator.build_sample_receipts()
    invalid_status = copy.deepcopy(passed_receipt)
    invalid_status["status"] = "failed"
    invalid_check = copy.deepcopy(passed_receipt)
    invalid_check["checks"][0]["passed"] = False

    status_errors = validator.validate_receipt(invalid_status)
    check_errors = validator.validate_receipt(invalid_check)

    assert any("status must be passed" in error for error in status_errors)
    assert any("passed does not match return_code" in error for error in check_errors)
    assert len(status_errors) >= 1


def test_load_schema_rejects_non_object_json(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_schema(schema_path)

    assert schema_path.exists()
    assert schema_path.name == "schema.json"
