"""Tests for personal-assistant receipt validation.

Purpose: prove personal-assistant receipts record taken and not-taken actions
while rejecting raw private connector payloads and secret-like values.
Governance scope: receipt schema, redaction policy, P4/P5 approval gating,
raw payload denial, and bounded error reporting.
Dependencies: scripts.validate_personal_assistant_receipt.
Invariants:
  - Receipts record actions taken and actions not taken.
  - Secret values and raw private connector payloads are rejected.
  - P4/P5 allowed execution requires approval evidence.
  - Math receipts cannot imply connector use, payment, publication, or record writes.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_personal_assistant_receipt import (
    validate_personal_assistant_receipt,
    validate_personal_assistant_receipt_payload,
)

ROOT = Path(__file__).resolve().parent.parent
RECEIPT_PATH = ROOT / "examples" / "personal_assistant_receipt_draft_only.json"
MATH_RECEIPT_PATH = ROOT / "examples" / "personal_assistant_receipt_math_reasoning.json"


def test_personal_assistant_receipt_accepts_draft_only_fixture() -> None:
    result = validate_personal_assistant_receipt()

    assert result.valid is True
    assert result.receipt_id == "pa_receipt_email_draft_001"
    assert result.actions_taken_count == 2
    assert result.actions_not_taken_count == 3
    assert result.errors == ()


def test_personal_assistant_receipt_accepts_math_reasoning_fixture() -> None:
    result = validate_personal_assistant_receipt(receipt_path=MATH_RECEIPT_PATH)
    receipt = _load_json(MATH_RECEIPT_PATH)

    assert result.valid is True
    assert result.receipt_id == "pa_receipt_math_reasoning_001"
    assert result.actions_taken_count == 4
    assert result.actions_not_taken_count == 7
    assert receipt["connectors_used"] == []
    assert receipt["private_payload_policy"]["connector_payload_projection"] == "no_connector_payload"
    assert receipt["metadata"]["money_movement_allowed"] is False


def test_math_receipt_rejects_effect_bearing_overclaim() -> None:
    receipt = _load_json(MATH_RECEIPT_PATH)
    receipt["connectors_used"] = ["stripe"]
    receipt["approval_required"] = True
    receipt["actions_taken"].append("payment_moved")
    receipt["actions_not_taken"].remove("publication_not_performed")
    receipt["private_payload_policy"]["connector_payload_projection"] = "digest_only"

    errors = validate_personal_assistant_receipt_payload(receipt)

    assert "math receipt cannot record connectors_used" in errors
    assert "math receipt cannot require approval for planning-only work" in errors
    assert "math receipt must use no_connector_payload projection" in errors
    assert any("actions_taken imply forbidden effects" in error and "payment" in error for error in errors)
    assert any("actions_not_taken missing forbidden-effect witnesses" in error and "publication" in error for error in errors)


def test_personal_assistant_receipt_requires_actions_taken_and_not_taken() -> None:
    receipt = _load_json(RECEIPT_PATH)
    receipt["actions_taken"] = []
    receipt["actions_not_taken"] = []

    errors = validate_personal_assistant_receipt_payload(receipt)

    assert "actions_taken must be non-empty" in errors
    assert "actions_not_taken must be non-empty" in errors
    assert len(errors) == 2


def test_personal_assistant_receipt_rejects_secret_values_and_raw_payloads() -> None:
    receipt = _load_json(RECEIPT_PATH)
    receipt["metadata"]["raw_private_connector_payload"] = {"subject": "private mailbox body"}
    receipt["metadata"]["operator_token_probe"] = "Bearer secret-token-value"

    errors = validate_personal_assistant_receipt_payload(receipt)

    assert any("raw private connector payload field is forbidden" in error for error in errors)
    assert any("secret-like value must not be serialized" in error for error in errors)
    assert receipt["private_payload_policy"]["raw_private_payload_serialized"] is False


def test_personal_assistant_receipt_p4_allowed_execution_requires_approval() -> None:
    receipt = _load_json(RECEIPT_PATH)
    receipt["risk_level"] = "P4"
    receipt["approval_required"] = True
    receipt["approval_ref"] = ""
    receipt["decision"] = "allowed"

    errors = validate_personal_assistant_receipt_payload(receipt)

    assert "allowed approval-required receipt must include approval_ref" in errors
    assert "P4 receipt requires explicit approval" not in errors
    assert any("approval" in error for error in errors)


def test_personal_assistant_receipt_missing_file_error_is_bounded(tmp_path: Path) -> None:
    missing_path = tmp_path / "private-secret-receipt.json"

    result = validate_personal_assistant_receipt(receipt_path=missing_path)
    serialized = json.dumps(result.as_dict(), sort_keys=True)

    assert result.valid is False
    assert result.receipt_path == "private-secret-receipt.json"
    assert "personal-assistant receipt could not be read" in result.errors
    assert str(tmp_path) not in serialized
    assert "private-secret-receipt" not in json.dumps(result.errors, sort_keys=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
