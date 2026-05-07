"""Tests for finance email/calendar binding receipt validation.

Purpose: prove finance token presence receipts are schema-compatible, redacted,
and internally consistent before live handoff execution.
Governance scope: finance approval handoff token binding, redacted receipt
validation, ready derivation, and strict promotion gating.
Dependencies: scripts.validate_finance_approval_email_calendar_binding_receipt.
Invariants:
  - Ready receipts pass when one accepted token is present.
  - Blocked receipts are valid but fail require-ready validation.
  - Value serialization and present-name drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_finance_approval_email_calendar_binding_receipt import (
    emit_finance_approval_email_calendar_binding_receipt,
    write_finance_email_calendar_binding_receipt,
)
from scripts.validate_finance_approval_email_calendar_binding_receipt import (
    main,
    validate_finance_approval_email_calendar_binding_receipt,
)


def test_validate_finance_binding_receipt_accepts_ready_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-email-calendar-binding.json"
    receipt, emit_errors = emit_finance_approval_email_calendar_binding_receipt(
        env_reader=lambda name: "present" if name == "EMAIL_CALENDAR_CONNECTOR_TOKEN" else "",
    )
    write_finance_email_calendar_binding_receipt(receipt, receipt_path)

    result = validate_finance_approval_email_calendar_binding_receipt(receipt_path=receipt_path)

    assert emit_errors == ()
    assert result.valid is True
    assert result.ready is True
    assert result.binding_count == 4
    assert result.present_binding_names == ("EMAIL_CALENDAR_CONNECTOR_TOKEN",)


def test_validate_finance_binding_receipt_allows_blocked_non_strict_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-email-calendar-binding.json"
    receipt, emit_errors = emit_finance_approval_email_calendar_binding_receipt(env_reader=lambda name: "")
    write_finance_email_calendar_binding_receipt(receipt, receipt_path)

    result = validate_finance_approval_email_calendar_binding_receipt(receipt_path=receipt_path)

    assert emit_errors == ()
    assert result.valid is True
    assert result.ready is False
    assert result.binding_count == 4
    assert result.present_binding_names == ()


def test_validate_finance_binding_receipt_require_ready_blocks_absent_tokens(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-email-calendar-binding.json"
    receipt, emit_errors = emit_finance_approval_email_calendar_binding_receipt(env_reader=lambda name: "")
    write_finance_email_calendar_binding_receipt(receipt, receipt_path)

    result = validate_finance_approval_email_calendar_binding_receipt(
        receipt_path=receipt_path,
        require_ready=True,
    )

    assert emit_errors == ()
    assert result.valid is False
    assert result.ready is False
    assert any("ready must be true" in error for error in result.errors)


def test_validate_finance_binding_receipt_rejects_value_serialization(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-email-calendar-binding.json"
    receipt, emit_errors = emit_finance_approval_email_calendar_binding_receipt(
        env_reader=lambda name: "present" if name == "EMAIL_CALENDAR_CONNECTOR_TOKEN" else "",
    )
    payload = receipt.as_dict()
    payload["bindings"][0]["value_serialized"] = True
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_email_calendar_binding_receipt(receipt_path=receipt_path)

    assert emit_errors == ()
    assert result.valid is False
    assert any("value_serialized" in error for error in result.errors)


def test_validate_finance_binding_receipt_rejects_present_name_drift(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-email-calendar-binding.json"
    receipt, emit_errors = emit_finance_approval_email_calendar_binding_receipt(
        env_reader=lambda name: "present" if name == "EMAIL_CALENDAR_CONNECTOR_TOKEN" else "",
    )
    payload = receipt.as_dict()
    payload["present_binding_names"] = []
    payload["ready"] = False
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_email_calendar_binding_receipt(receipt_path=receipt_path)

    assert emit_errors == ()
    assert result.valid is False
    assert any("present_binding_names must match" in error for error in result.errors)


def test_validate_finance_binding_receipt_cli_outputs_json(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "finance-email-calendar-binding.json"
    receipt, emit_errors = emit_finance_approval_email_calendar_binding_receipt(
        env_reader=lambda name: "present" if name == "EMAIL_CALENDAR_CONNECTOR_TOKEN" else "",
    )
    write_finance_email_calendar_binding_receipt(receipt, receipt_path)

    exit_code = main(["--receipt", str(receipt_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert emit_errors == ()
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is True
    assert payload["present_binding_names"] == ["EMAIL_CALENDAR_CONNECTOR_TOKEN"]


def test_validate_finance_binding_receipt_missing_file_error_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "secret-receipt-path.json"

    result = validate_finance_approval_email_calendar_binding_receipt(receipt_path=receipt_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "finance email/calendar binding receipt could not be read" in result.errors
    assert "secret-receipt-path" not in serialized_errors


def test_validate_finance_binding_receipt_json_parse_error_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-email-calendar-binding.json"
    receipt_path.write_text('{"receipt_id": "secret-json-token"', encoding="utf-8")

    result = validate_finance_approval_email_calendar_binding_receipt(receipt_path=receipt_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "finance email/calendar binding receipt must be JSON" in result.errors
    assert "secret-json-token" not in serialized_errors
