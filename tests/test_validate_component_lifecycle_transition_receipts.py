"""Tests for Component Harness lifecycle transition receipt validation.

Purpose: prove lifecycle state transitions are receipt-bound, evidence-backed,
and denied live authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_lifecycle_transition_receipts and
foundation Component Harness fixtures.
Invariants: every registered component has one current-state receipt, receipt
states match registry states, evidence exists, and live authority stays false.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_component_lifecycle_transition_receipts import (
    DEFAULT_OUTPUT,
    DEFAULT_RECEIPTS,
    validate_component_lifecycle_transition_receipts,
    write_component_lifecycle_transition_receipt_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_RECEIPTS.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    receipt_path = tmp_path / "component_lifecycle_transition_receipts.json"
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def _receipts(payload: dict[str, object]) -> list[dict[str, object]]:
    receipts = payload["transition_receipts"]
    assert isinstance(receipts, list)
    return receipts


def test_component_lifecycle_transition_receipts_validate_and_write(tmp_path: Path) -> None:
    validation = validate_component_lifecycle_transition_receipts()
    output_path = tmp_path / "component-lifecycle-transition-receipts-validation.json"

    written_path = write_component_lifecycle_transition_receipt_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.receipt_count == 10
    assert validation.component_count == 10
    assert validation.allowed_transition_count == 10
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_lifecycle_transition_receipts_validation.json"


def test_component_lifecycle_transition_receipts_reject_missing_component_receipt(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["transition_receipts"] = [
        receipt for receipt in _receipts(payload) if receipt.get("component_id") != "snet"
    ]

    validation = validate_component_lifecycle_transition_receipts(receipt_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert validation.receipt_count == 9
    assert "registered components missing lifecycle receipts ['snet']" in serialized_errors


def test_component_lifecycle_transition_receipts_reject_state_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    first_receipt = _receipts(payload)[0]
    first_receipt["to_state"] = "approved_live_action"
    first_receipt["operator_approval_required"] = True

    validation = validate_component_lifecycle_transition_receipts(receipt_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "approved_live_action" in serialized_errors
    assert "to_state must match registry lifecycle_state registered" in serialized_errors
    assert "not allowed" in serialized_errors


def test_component_lifecycle_transition_receipts_reject_live_authority_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    receipt = _receipts(payload)[1]
    authority_guardrails = receipt["authority_guardrails"]
    assert isinstance(authority_guardrails, dict)
    authority_guardrails["can_execute"] = True
    receipt["receipt_is_not_execution_authority"] = False
    receipt["external_effect"] = True
    receipt["blocked_actions"] = ["connector_call"]

    validation = validate_component_lifecycle_transition_receipts(receipt_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_guardrails.can_execute must be false" in serialized_errors
    assert "receipt_is_not_execution_authority must be true" in serialized_errors
    assert "external_effect" in serialized_errors
    assert "terminal_closure" in serialized_errors


def test_component_lifecycle_transition_receipts_reject_missing_evidence(tmp_path: Path) -> None:
    payload = _default_payload()
    receipt = _receipts(payload)[2]
    receipt["evidence_refs"] = ["docs/missing-component-evidence.md"]

    validation = validate_component_lifecycle_transition_receipts(receipt_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_ref missing on disk" in serialized_errors
    assert "docs/missing-component-evidence.md" in serialized_errors
