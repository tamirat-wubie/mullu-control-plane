"""Tests for durable Gmail write-authority rehearsal receipts.

Purpose: prove Gmail write authority remains approval-gated without creating
drafts, sends, external provider calls, mailbox writes, or secret disclosure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.produce_durable_gmail_write_authority_rehearsal_receipt
and scripts.validate_durable_gmail_write_authority_rehearsal_receipt.
Invariants:
  - Send without approval is blocked.
  - Draft/send split is preserved.
  - Write authority is not promoted by repository-local rehearsal.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_durable_gmail_write_authority_rehearsal_receipt import (
    produce_write_authority_rehearsal_receipt,
)
from scripts.validate_durable_gmail_write_authority_rehearsal_receipt import (
    validate_write_authority_rehearsal_receipt,
)


def _write_receipt(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_rehearsal(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "receipt_id": "durable_gmail_write_authority_rehearsal_receipt",
        "adapter_id": "communication.gmail_oauth",
        "connector_id": "gmail",
        "mode": "foundation-local",
        "checked_at": "2026-06-13T00:00:00Z",
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "operation_family": "send_with_approval",
        "rehearsal_case": "send_without_approval_blocked",
        "approval_required": True,
        "approval_gate_result": "blocked_without_approval",
        "approval_receipt_ref": "",
        "account_binding_receipt_ref": ".change_assurance/durable_gmail_account_binding_receipt.json",
        "source_live_receipt_ref": ".change_assurance/durable_gmail_oauth_live_receipt.json",
        "required_scope_ref": "oauth:gmail.send",
        "draft_send_split_enforced": True,
        "send_requires_approval": True,
        "external_provider_call_performed": False,
        "external_mailbox_write_performed": False,
        "external_draft_created": False,
        "external_send_performed": False,
        "credential_values_disclosed": False,
        "production_ready_claimed": False,
        "write_authority_claimed": False,
        "calendar_authority_claimed": False,
        "blockers": [],
    }
    payload.update(overrides)
    return payload


def test_producer_writes_ready_non_effect_write_rehearsal(tmp_path: Path) -> None:
    output_path = tmp_path / "write-rehearsal.json"
    payload = produce_write_authority_rehearsal_receipt(
        environment={
            "MULLU_VALIDATION_TIMESTAMP": "2026-06-13T00:00:00Z",
            "MULLU_GMAIL_ACCOUNT_BINDING_RECEIPT_REF": ".change_assurance/account-binding.json",
            "MULLU_GMAIL_WRITE_SOURCE_LIVE_RECEIPT_REF": ".change_assurance/live-receipt.json",
        },
        output_path=output_path,
    )
    serialized = output_path.read_text(encoding="utf-8")
    validation = validate_write_authority_rehearsal_receipt(output_path, now="2026-06-13T00:00:00Z")

    assert payload["status"] == "passed"
    assert payload["approval_gate_result"] == "blocked_without_approval"
    assert payload["draft_send_split_enforced"] is True
    assert payload["external_send_performed"] is False
    assert validation["ready_for_write_rehearsal"] is True
    assert validation["ready_for_write_authority"] is False
    assert "refresh_token=" not in serialized
    assert "client_secret=" not in serialized


def test_stale_write_rehearsal_blocks_readiness(tmp_path: Path) -> None:
    receipt_path = tmp_path / "write-rehearsal.json"
    _write_receipt(receipt_path, _write_rehearsal(checked_at="2026-05-01T00:00:00Z"))

    report = validate_write_authority_rehearsal_receipt(
        receipt_path,
        now="2026-06-13T00:00:00Z",
        max_age_days=14,
    )

    assert report["valid"] is True
    assert report["fresh"] is False
    assert report["ready_for_write_rehearsal"] is False
    assert report["freshness_status"] == "stale"
    assert "gmail_write_rehearsal_age_exceeds_max_age" in report["blockers"]


def test_external_send_overclaim_is_blocked(tmp_path: Path) -> None:
    receipt_path = tmp_path / "write-rehearsal.json"
    _write_receipt(receipt_path, _write_rehearsal(external_send_performed=True))

    report = validate_write_authority_rehearsal_receipt(receipt_path, now="2026-06-13T00:00:00Z")

    assert report["valid"] is False
    assert report["ready_for_write_rehearsal"] is False
    assert "gmail_write_rehearsal_invalid" in report["blockers"]
    assert any("external_send_performed false" in error for error in report["errors"])


def test_missing_draft_send_split_is_blocked(tmp_path: Path) -> None:
    receipt_path = tmp_path / "write-rehearsal.json"
    _write_receipt(receipt_path, _write_rehearsal(draft_send_split_enforced=False))

    report = validate_write_authority_rehearsal_receipt(receipt_path, now="2026-06-13T00:00:00Z")

    assert report["valid"] is False
    assert report["ready_for_write_rehearsal"] is False
    assert any("draft/send split" in error for error in report["errors"])


def test_approval_receipt_overclaim_is_blocked_for_no_approval_case(tmp_path: Path) -> None:
    receipt_path = tmp_path / "write-rehearsal.json"
    _write_receipt(receipt_path, _write_rehearsal(approval_receipt_ref="approval://gmail/send/001"))

    report = validate_write_authority_rehearsal_receipt(receipt_path, now="2026-06-13T00:00:00Z")

    assert report["valid"] is False
    assert report["ready_for_write_rehearsal"] is False
    assert any("must not attach an approval receipt" in error for error in report["errors"])


def test_secret_marker_and_raw_mailbox_are_blocked_without_disclosure(tmp_path: Path) -> None:
    secret_path = tmp_path / "secret.json"
    mailbox_path = tmp_path / "mailbox.json"
    _write_receipt(secret_path, _write_rehearsal(leak="client_secret=raw-secret"))
    _write_receipt(mailbox_path, _write_rehearsal(recipient="operator@example.com"))

    secret_report = validate_write_authority_rehearsal_receipt(secret_path, now="2026-06-13T00:00:00Z")
    mailbox_report = validate_write_authority_rehearsal_receipt(mailbox_path, now="2026-06-13T00:00:00Z")
    serialized_secret_report = json.dumps(secret_report, sort_keys=True)
    serialized_mailbox_report = json.dumps(mailbox_report, sort_keys=True)

    assert secret_report["valid"] is False
    assert mailbox_report["valid"] is False
    assert "gmail_write_rehearsal_contains_secret_marker" in secret_report["blockers"]
    assert "gmail_write_rehearsal_contains_raw_mailbox_address" in mailbox_report["blockers"]
    assert "raw-secret" not in serialized_secret_report
    assert "operator@example.com" not in serialized_mailbox_report


def test_missing_receipt_error_is_bounded(tmp_path: Path) -> None:
    report = validate_write_authority_rehearsal_receipt(
        tmp_path / "missing.json",
        now="2026-06-13T00:00:00Z",
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["valid"] is False
    assert report["ready_for_write_rehearsal"] is False
    assert "gmail_write_rehearsal_receipt_unavailable" in report["blockers"]
    assert str(tmp_path) not in serialized
    assert "missing.json" in serialized
