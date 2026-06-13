"""Tests for durable Gmail revocation recovery rehearsal receipts.

Purpose: prove Gmail OAuth invalid-grant recovery can be rehearsed without
destructive provider revocation, mailbox writes, or secret disclosure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.produce_durable_gmail_revocation_recovery_rehearsal_receipt
and scripts.validate_durable_gmail_revocation_recovery_rehearsal_receipt.
Invariants:
  - Invalid-grant recovery requires reauthorization.
  - Rehearsal receipts never claim live destructive revocation.
  - Secret-shaped values are blocked before validation output.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_durable_gmail_revocation_recovery_rehearsal_receipt import (
    produce_revocation_recovery_rehearsal_receipt,
)
from scripts.validate_durable_gmail_revocation_recovery_rehearsal_receipt import (
    validate_revocation_recovery_rehearsal_receipt,
)


def _write_receipt(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rehearsal_receipt(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "receipt_id": "durable_gmail_revocation_recovery_rehearsal_receipt",
        "adapter_id": "communication.gmail_oauth",
        "connector_id": "gmail",
        "mode": "foundation-local",
        "checked_at": "2026-06-13T00:00:00Z",
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "refresh_failure_case": "invalid_grant",
        "classified_refresh_status": "refresh_token_revoked_or_expired",
        "requires_reauthorization": True,
        "retryable": False,
        "recovery_action": "halt_for_reauthorization",
        "refresh_token_storage_ref": "receipt:gmail-refresh-token-storage",
        "revocation_recovery_ref": "witness:gmail-revocation-recovery",
        "external_provider_call_performed": False,
        "destructive_revocation_performed": False,
        "external_mailbox_write_performed": False,
        "credential_values_disclosed": False,
        "production_ready_claimed": False,
        "blockers": [],
    }
    payload.update(overrides)
    return payload


def test_producer_writes_ready_non_destructive_rehearsal(tmp_path: Path) -> None:
    output_path = tmp_path / "rehearsal.json"
    payload = produce_revocation_recovery_rehearsal_receipt(
        environment={
            "MULLU_VALIDATION_TIMESTAMP": "2026-06-13T00:00:00Z",
            "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF": "receipt:gmail-refresh-storage",
            "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF": "witness:gmail-recovery-rehearsal",
        },
        output_path=output_path,
    )
    serialized = output_path.read_text(encoding="utf-8")
    validation = validate_revocation_recovery_rehearsal_receipt(output_path, now="2026-06-13T00:00:00Z")

    assert payload["status"] == "passed"
    assert payload["classified_refresh_status"] == "refresh_token_revoked_or_expired"
    assert payload["requires_reauthorization"] is True
    assert payload["destructive_revocation_performed"] is False
    assert validation["ready_for_recovery_rehearsal"] is True
    assert "refresh_token=" not in serialized
    assert "client_secret=" not in serialized


def test_stale_rehearsal_blocks_readiness(tmp_path: Path) -> None:
    receipt_path = tmp_path / "rehearsal.json"
    _write_receipt(receipt_path, _rehearsal_receipt(checked_at="2026-05-01T00:00:00Z"))

    report = validate_revocation_recovery_rehearsal_receipt(
        receipt_path,
        now="2026-06-13T00:00:00Z",
        max_age_days=14,
    )

    assert report["valid"] is True
    assert report["fresh"] is False
    assert report["ready_for_recovery_rehearsal"] is False
    assert report["freshness_status"] == "stale"
    assert "revocation_rehearsal_age_exceeds_max_age" in report["blockers"]


def test_destructive_revocation_overclaim_is_blocked(tmp_path: Path) -> None:
    receipt_path = tmp_path / "rehearsal.json"
    _write_receipt(receipt_path, _rehearsal_receipt(destructive_revocation_performed=True))

    report = validate_revocation_recovery_rehearsal_receipt(receipt_path, now="2026-06-13T00:00:00Z")

    assert report["valid"] is False
    assert report["fresh"] is False
    assert report["ready_for_recovery_rehearsal"] is False
    assert "revocation_rehearsal_invalid" in report["blockers"]
    assert any("must not claim destructive revocation" in error for error in report["errors"])


def test_wrong_recovery_action_is_blocked(tmp_path: Path) -> None:
    receipt_path = tmp_path / "rehearsal.json"
    _write_receipt(receipt_path, _rehearsal_receipt(recovery_action="retry_with_backoff"))

    report = validate_revocation_recovery_rehearsal_receipt(receipt_path, now="2026-06-13T00:00:00Z")

    assert report["valid"] is False
    assert report["ready_for_recovery_rehearsal"] is False
    assert any("halt for reauthorization" in error for error in report["errors"])


def test_secret_marker_is_blocked_without_disclosure(tmp_path: Path) -> None:
    receipt_path = tmp_path / "rehearsal.json"
    _write_receipt(receipt_path, _rehearsal_receipt(leak="refresh_token=raw-secret"))

    report = validate_revocation_recovery_rehearsal_receipt(receipt_path, now="2026-06-13T00:00:00Z")
    serialized = json.dumps(report, sort_keys=True)

    assert report["valid"] is False
    assert report["ready_for_recovery_rehearsal"] is False
    assert "revocation_rehearsal_contains_secret_marker" in report["blockers"]
    assert "raw-secret" not in serialized


def test_missing_receipt_error_is_bounded(tmp_path: Path) -> None:
    report = validate_revocation_recovery_rehearsal_receipt(
        tmp_path / "missing.json",
        now="2026-06-13T00:00:00Z",
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["valid"] is False
    assert report["ready_for_recovery_rehearsal"] is False
    assert "revocation_rehearsal_receipt_unavailable" in report["blockers"]
    assert str(tmp_path) not in serialized
    assert "missing.json" in serialized
