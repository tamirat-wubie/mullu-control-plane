"""Tests for finance email/calendar live receipt validation.

Purpose: prove finance live handoff requires read-only email/calendar adapter
evidence before promotion.
Governance scope: finance live connector evidence, external-write rejection,
schema validation, and strict readiness gating.
Dependencies: scripts.validate_finance_approval_email_calendar_live_receipt.
Invariants:
  - Passed read-only receipts are ready.
  - Failed receipts remain valid blocked evidence in non-strict validation.
  - External writes and adapter drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_finance_approval_email_calendar_live_receipt import (
    main,
    validate_finance_approval_email_calendar_live_receipt,
)


def test_validate_finance_email_calendar_live_receipt_accepts_read_only_pass(tmp_path: Path) -> None:
    receipt_path = tmp_path / "email-calendar-live-receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    result = validate_finance_approval_email_calendar_live_receipt(receipt_path=receipt_path, require_ready=True)

    assert result.valid is True
    assert result.ready is True
    assert result.adapter_id == "communication.email_calendar_worker"
    assert result.status == "passed"
    assert result.verification_status == "passed"
    assert result.external_write is False
    assert result.provider_operation == "email.search"
    assert result.blockers == ()


def test_validate_finance_email_calendar_live_receipt_allows_blocked_failed_probe(tmp_path: Path) -> None:
    receipt_path = tmp_path / "email-calendar-live-receipt.json"
    payload = _ready_receipt() | {
        "status": "failed",
        "verification_status": "failed",
        "blockers": ["email_calendar_probe_exception"],
        "provider_operation": "",
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_email_calendar_live_receipt(receipt_path=receipt_path)

    assert result.valid is True
    assert result.ready is False
    assert result.status == "failed"
    assert result.verification_status == "failed"
    assert result.blockers == ("email_calendar_probe_exception",)


def test_validate_finance_email_calendar_live_receipt_require_ready_blocks_failed_probe(tmp_path: Path) -> None:
    receipt_path = tmp_path / "email-calendar-live-receipt.json"
    payload = _ready_receipt() | {
        "status": "failed",
        "verification_status": "failed",
        "blockers": ["email_calendar_probe_exception"],
        "provider_operation": "",
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_email_calendar_live_receipt(receipt_path=receipt_path, require_ready=True)

    assert result.valid is False
    assert result.ready is False
    assert "finance email/calendar live receipt ready must be true" in result.errors


def test_validate_finance_email_calendar_live_receipt_rejects_external_write(tmp_path: Path) -> None:
    receipt_path = tmp_path / "email-calendar-live-receipt.json"
    payload = _ready_receipt() | {
        "provider_operation": "email.send.with_approval",
        "external_write": True,
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_email_calendar_live_receipt(receipt_path=receipt_path)

    assert result.valid is False
    assert result.ready is False
    assert any("external_write" in error for error in result.errors)


def test_validate_finance_email_calendar_live_receipt_cli_outputs_json(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "email-calendar-live-receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    exit_code = main(["--receipt", str(receipt_path), "--require-ready", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is True
    assert payload["provider_operation"] == "email.search"


def _ready_receipt() -> dict[str, object]:
    return {
        "receipt_id": "email-calendar-live-receipt-test",
        "adapter_id": "communication.email_calendar_worker",
        "status": "passed",
        "verification_status": "passed",
        "checked_at": "2026-05-01T12:00:00+00:00",
        "connector_id": "gmail",
        "provider_operation": "email.search",
        "external_write": False,
        "worker_receipt": {
            "verification_status": "passed",
            "capability_id": "email.search",
            "external_write": False,
        },
        "blockers": [],
    }
