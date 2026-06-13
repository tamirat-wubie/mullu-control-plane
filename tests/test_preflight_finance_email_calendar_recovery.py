"""Tests for finance email/calendar recovery preflight.

Purpose: prove failed live receipt recovery actions map to concrete redacted
environment and worker reachability checks before rerunning the live probe.
Governance scope: finance live handoff recovery, secret redaction, read-only
scope review, and bounded operator evidence.
Dependencies: scripts.preflight_finance_email_calendar_recovery.
Invariants:
  - Missing worker/token/scope evidence blocks rerun readiness.
  - Ready evidence reports only names and counts, not values.
  - Optional worker probing can prove endpoint reachability.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.preflight_finance_email_calendar_recovery import (
    main,
    preflight_finance_email_calendar_recovery,
    write_finance_email_calendar_recovery_preflight,
)


def test_recovery_preflight_blocks_missing_worker_and_token(tmp_path: Path) -> None:
    receipt_path = _write_failed_receipt(tmp_path)

    result = preflight_finance_email_calendar_recovery(
        receipt_path=receipt_path,
        env_reader=lambda name: "",
    )

    assert result.ok is True
    assert result.ready_to_rerun_probe is False
    assert result.receipt_path == "email-calendar-live-receipt.json"
    assert result.failure_class == "worker_probe_failed"
    assert "verify_email_calendar_worker_reachable" in result.blockers
    assert "verify_connector_token_present" in result.blockers
    assert "verify_connector_scope_read_only" in result.blockers


def test_recovery_preflight_accepts_redacted_ready_bindings(tmp_path: Path) -> None:
    receipt_path = _write_failed_receipt(tmp_path)

    result = preflight_finance_email_calendar_recovery(
        receipt_path=receipt_path,
        env_reader=_ready_env,
    )
    serialized = json.dumps(result.as_dict(), sort_keys=True)

    assert result.ok is True
    assert result.ready_to_rerun_probe is True
    assert result.blockers == ()
    assert _check(result, "verify_email_calendar_worker_reachable").passed is True
    assert _check(result, "verify_connector_token_present").detail == "present accepted token bindings=1"
    assert _check(result, "verify_connector_scope_read_only").passed is True
    assert result.receipt_path == "email-calendar-live-receipt.json"
    assert "secret-token-value" not in serialized
    assert "https://worker.internal/email-calendar" not in serialized
    assert str(tmp_path) not in serialized


def test_recovery_preflight_accepts_google_calendar_readonly_scope(tmp_path: Path) -> None:
    receipt_path = _write_failed_receipt(tmp_path)

    def env_reader(name: str) -> str:
        values = {
            "MULLU_EMAIL_CALENDAR_WORKER_URL": "https://worker.internal/email-calendar",
            "MULLU_EMAIL_CALENDAR_WORKER_SECRET": "secret-worker-value",
            "GOOGLE_CALENDAR_ACCESS_TOKEN": "secret-token-value",
            "GOOGLE_CALENDAR_SCOPE_ID": "calendar.events.readonly",
        }
        return values.get(name, "")

    result = preflight_finance_email_calendar_recovery(
        receipt_path=receipt_path,
        env_reader=env_reader,
    )

    assert result.ok is True
    assert result.ready_to_rerun_probe is True
    assert result.blockers == ()
    assert _check(result, "verify_connector_scope_read_only").passed is True


def test_recovery_preflight_restores_missing_required_actions(tmp_path: Path) -> None:
    receipt_path = tmp_path / "email-calendar-live-receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "adapter_id": "communication.email_calendar_worker",
                "failure_class": "worker_probe_failed",
                "recovery_actions": ["verify_connector_token_present"],
                "status": "failed",
            }
        ),
        encoding="utf-8",
    )

    result = preflight_finance_email_calendar_recovery(
        receipt_path=receipt_path,
        env_reader=lambda name: "",
    )

    assert "verify_email_calendar_worker_reachable" in result.blockers
    assert "verify_connector_token_present" in result.blockers
    assert "verify_connector_scope_read_only" in result.blockers


def test_recovery_preflight_worker_probe_failure_blocks_rerun(tmp_path: Path) -> None:
    receipt_path = _write_failed_receipt(tmp_path)

    result = preflight_finance_email_calendar_recovery(
        receipt_path=receipt_path,
        env_reader=_ready_env,
        probe_worker=True,
        worker_probe=lambda endpoint: False,
    )

    assert result.ready_to_rerun_probe is False
    assert result.blockers == ("verify_email_calendar_worker_reachable",)
    assert _check(result, "verify_email_calendar_worker_reachable").detail == (
        "worker endpoint did not respond to reachability probe"
    )


def test_recovery_preflight_cli_outputs_redacted_json(tmp_path: Path, monkeypatch, capsys) -> None:
    receipt_path = _write_failed_receipt(tmp_path)
    output_path = tmp_path / "finance_email_calendar_recovery_preflight.json"
    monkeypatch.setenv("MULLU_EMAIL_CALENDAR_WORKER_URL", "https://worker.internal/email-calendar")
    monkeypatch.setenv("MULLU_EMAIL_CALENDAR_WORKER_SECRET", "secret-worker-value")
    monkeypatch.setenv("EMAIL_CALENDAR_CONNECTOR_TOKEN", "secret-token-value")
    monkeypatch.setenv("EMAIL_CALENDAR_CONNECTOR_SCOPE_ID", "gmail.readonly")

    exit_code = main(["--receipt", str(receipt_path), "--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, sort_keys=True)

    assert exit_code == 0
    assert payload["ready_to_rerun_probe"] is True
    assert written_payload == payload
    assert payload["receipt_path"] == "email-calendar-live-receipt.json"
    assert payload["blockers"] == []
    assert "secret-worker-value" not in serialized
    assert "secret-token-value" not in serialized
    assert "worker.internal" not in serialized
    assert str(tmp_path) not in serialized


def test_recovery_preflight_writer_persists_redacted_receipt(tmp_path: Path) -> None:
    receipt_path = _write_failed_receipt(tmp_path)
    output_path = tmp_path / "recovery_preflight.json"
    result = preflight_finance_email_calendar_recovery(
        receipt_path=receipt_path,
        env_reader=_ready_env,
    )

    written = write_finance_email_calendar_recovery_preflight(result, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, sort_keys=True)

    assert written == output_path
    assert payload["ready_to_rerun_probe"] is True
    assert payload["blockers"] == []
    assert "secret-token-value" not in serialized
    assert "worker.internal" not in serialized


def test_recovery_preflight_missing_receipt_path_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "missing-email-calendar-live-receipt.json"

    result = preflight_finance_email_calendar_recovery(
        receipt_path=receipt_path,
        env_reader=lambda name: "",
    )
    serialized = json.dumps(result.as_dict(), sort_keys=True)

    assert result.ok is False
    assert result.ready_to_rerun_probe is False
    assert result.receipt_path == "missing-email-calendar-live-receipt.json"
    assert result.receipt_status == ""
    assert result.errors == ("finance email/calendar live receipt could not be read",)
    assert str(tmp_path) not in serialized


def test_recovery_preflight_malformed_receipt_path_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "bad-email-calendar-live-receipt.json"
    receipt_path.write_text('{"receipt_id": "secret-email-calendar-token"', encoding="utf-8")

    result = preflight_finance_email_calendar_recovery(
        receipt_path=receipt_path,
        env_reader=lambda name: "",
    )
    serialized = json.dumps(result.as_dict(), sort_keys=True)

    assert result.ok is False
    assert result.ready_to_rerun_probe is False
    assert result.receipt_path == "bad-email-calendar-live-receipt.json"
    assert result.receipt_status == ""
    assert result.errors == ("finance email/calendar live receipt must be JSON",)
    assert str(tmp_path) not in serialized


def _write_failed_receipt(tmp_path: Path) -> Path:
    receipt_path = tmp_path / "email-calendar-live-receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "adapter_id": "communication.email_calendar_worker",
                "blockers": ["email_calendar_worker_probe_failed"],
                "checked_at": "2026-05-01T12:00:00+00:00",
                "error": "email_calendar_worker_probe_failed",
                "external_write": False,
                "failure_class": "worker_probe_failed",
                "provider_operation": "email.search",
                "receipt_id": "email-calendar-live-receipt-test",
                "recovery_actions": [
                    "verify_email_calendar_worker_reachable",
                    "verify_connector_token_present",
                    "verify_connector_scope_read_only",
                    "rerun_email_calendar_live_receipt_probe",
                ],
                "status": "failed",
                "verification_status": "failed",
            }
        ),
        encoding="utf-8",
    )
    return receipt_path


def _ready_env(name: str) -> str:
    values = {
        "MULLU_EMAIL_CALENDAR_WORKER_URL": "https://worker.internal/email-calendar",
        "MULLU_EMAIL_CALENDAR_WORKER_SECRET": "secret-worker-value",
        "EMAIL_CALENDAR_CONNECTOR_TOKEN": "secret-token-value",
        "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID": "gmail.readonly",
    }
    return values.get(name, "")


def _check(result, action: str):
    return next(check for check in result.checks if check.action == action)
