"""Tests for finance email/calendar connector binding receipts.

Purpose: prove finance live handoff token presence is recorded without
serializing connector token values.
Governance scope: finance approval handoff token binding, redacted receipts,
schema validation, and strict CLI behavior.
Dependencies: scripts.emit_finance_approval_email_calendar_binding_receipt.
Invariants:
  - One accepted connector token is sufficient for readiness.
  - Token values never appear in the receipt.
  - Strict mode fails when no accepted token is present.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_finance_approval_email_calendar_binding_receipt import (
    ACCEPTED_BINDING_NAMES,
    emit_finance_approval_email_calendar_binding_receipt,
    main,
    write_finance_email_calendar_binding_receipt,
)


def test_finance_email_calendar_binding_receipt_records_presence_without_values() -> None:
    receipt, errors = emit_finance_approval_email_calendar_binding_receipt(
        env_reader=lambda name: "secret-token-value" if name == "EMAIL_CALENDAR_CONNECTOR_TOKEN" else "",
    )
    payload = receipt.as_dict()
    serialized = json.dumps(payload, sort_keys=True)

    assert errors == ()
    assert receipt.ready is True
    assert receipt.binding_count == 4
    assert receipt.accepted_binding_names == ACCEPTED_BINDING_NAMES
    assert receipt.present_binding_names == ("EMAIL_CALENDAR_CONNECTOR_TOKEN",)
    assert "secret-token-value" not in serialized
    assert all(binding.value_serialized is False for binding in receipt.bindings)
    assert all(binding.receipt_projection == "name_and_presence_only" for binding in receipt.bindings)


def test_finance_email_calendar_binding_receipt_blocks_when_tokens_absent() -> None:
    receipt, errors = emit_finance_approval_email_calendar_binding_receipt(env_reader=lambda name: "")

    assert errors == ()
    assert receipt.ready is False
    assert receipt.present_binding_names == ()
    assert {binding.name for binding in receipt.bindings} == set(ACCEPTED_BINDING_NAMES)
    assert sum(1 for binding in receipt.bindings if binding.present) == 0


def test_finance_email_calendar_binding_receipt_writer_and_cli_strict(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    for env_name in ACCEPTED_BINDING_NAMES:
        monkeypatch.delenv(env_name, raising=False)
    output_path = tmp_path / "finance-email-calendar-binding.json"
    receipt, errors = emit_finance_approval_email_calendar_binding_receipt(env_reader=lambda name: "")

    written = write_finance_email_calendar_binding_receipt(receipt, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert errors == ()
    assert written == output_path
    assert exit_code == 2
    assert payload["ready"] is False
    assert stdout_payload["ready"] is False
    assert payload["present_binding_names"] == []


def test_finance_email_calendar_binding_receipt_schema_error_is_bounded(tmp_path: Path) -> None:
    schema_path = tmp_path / "secret-schema-path.json"

    receipt, errors = emit_finance_approval_email_calendar_binding_receipt(schema_path=schema_path)
    serialized_errors = json.dumps(errors, sort_keys=True)

    assert receipt.ready is False
    assert "finance email/calendar binding receipt schema could not be read" in errors
    assert "secret-schema-path" not in serialized_errors
