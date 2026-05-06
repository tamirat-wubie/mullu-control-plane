"""Tests for finance approval live handoff chain validation.

Purpose: prove the aggregate finance live handoff chain validator fails closed
when any child artifact validator fails.
Governance scope: closure run validation, preflight validation, handoff packet
validation, protocol manifest validation, and strict CLI behavior.
Dependencies: scripts.validate_finance_approval_live_handoff_chain.
Invariants:
  - Current generated artifact chain validates.
  - Broken closure-run artifacts fail the chain.
  - Broken preflight artifacts fail the chain.
  - Strict CLI returns nonzero for a failed chain.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.preflight_finance_approval_live_handoff import (
    preflight_finance_approval_live_handoff,
    write_finance_live_handoff_preflight_report,
)
from scripts.produce_finance_approval_handoff_packet import (
    produce_finance_approval_handoff_packet,
    write_finance_approval_handoff_packet,
)
from scripts.run_finance_approval_live_handoff_closure import (
    run_finance_approval_live_handoff_closure,
    write_finance_live_handoff_closure_run,
)
from scripts.validate_finance_approval_live_handoff_chain import (
    main,
    validate_finance_approval_live_handoff_chain,
    write_finance_live_handoff_chain_validation,
)


def test_finance_live_handoff_chain_accepts_current_artifacts() -> None:
    validation = validate_finance_approval_live_handoff_chain()

    assert validation.ok is True
    assert validation.blockers == ()
    assert validation.check_count == 5
    assert {check.name for check in validation.checks} == {
        "finance closure run schema validation",
        "finance email/calendar live receipt validation",
        "finance preflight schema validation",
        "finance handoff packet schema validation",
        "governance protocol manifest validation",
    }
    live_check = next(check for check in validation.checks if check.name == "finance email/calendar live receipt validation")
    assert "ready=False" in live_check.detail
    assert "status=failed" in live_check.detail


def test_finance_live_handoff_chain_rejects_invalid_closure_run(tmp_path: Path) -> None:
    closure_run_path, preflight_path, packet_path = _write_current_chain(tmp_path)
    closure_run = json.loads(closure_run_path.read_text(encoding="utf-8"))
    closure_run["commands"] = []
    closure_run["command_count"] = 0
    closure_run_path.write_text(json.dumps(closure_run), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_chain(
        closure_run_path=closure_run_path,
        preflight_path=preflight_path,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert "finance closure run schema validation" in validation.blockers


def test_finance_live_handoff_chain_rejects_invalid_preflight(tmp_path: Path) -> None:
    closure_run_path, preflight_path, packet_path = _write_current_chain(tmp_path)
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    preflight["blockers"] = []
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_chain(
        closure_run_path=closure_run_path,
        preflight_path=preflight_path,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert "finance preflight schema validation" in validation.blockers
    assert "finance handoff packet schema validation" in validation.blockers


def test_finance_live_handoff_chain_rejects_invalid_live_receipt(tmp_path: Path) -> None:
    closure_run_path, preflight_path, packet_path = _write_current_chain(tmp_path)
    live_receipt_path = tmp_path / "email_calendar_live_receipt.json"
    live_receipt_path.write_text(
        json.dumps(
            {
                "receipt_id": "email-calendar-live-receipt-test",
                "adapter_id": "communication.other_worker",
                "status": "passed",
                "verification_status": "passed",
                "checked_at": "2026-05-01T12:00:00+00:00",
                "external_write": False,
                "blockers": [],
            }
        ),
        encoding="utf-8",
    )

    validation = validate_finance_approval_live_handoff_chain(
        closure_run_path=closure_run_path,
        live_receipt_path=live_receipt_path,
        preflight_path=preflight_path,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert "finance email/calendar live receipt validation" in validation.blockers


def test_finance_live_handoff_chain_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    closure_run_path, preflight_path, packet_path = _write_current_chain(tmp_path)
    output_path = tmp_path / "chain_validation.json"
    closure_run = json.loads(closure_run_path.read_text(encoding="utf-8"))
    closure_run["status"] = "ready"
    closure_run_path.write_text(json.dumps(closure_run), encoding="utf-8")
    validation = validate_finance_approval_live_handoff_chain(
        closure_run_path=closure_run_path,
        preflight_path=preflight_path,
        packet_path=packet_path,
    )

    written = write_finance_live_handoff_chain_validation(validation, output_path)
    exit_code = main(
        [
            "--closure-run",
            str(closure_run_path),
            "--preflight",
            str(preflight_path),
            "--packet",
            str(packet_path),
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert validation.ok is False
    assert exit_code == 2
    assert payload["ok"] is False
    assert stdout_payload["blockers"] == list(validation.blockers)


def _write_current_chain(tmp_path: Path) -> tuple[Path, Path, Path]:
    closure_run_path = tmp_path / "finance_closure_run.json"
    preflight_path = tmp_path / "finance_preflight.json"
    packet_path = tmp_path / "finance_handoff_packet.json"
    write_finance_live_handoff_closure_run(run_finance_approval_live_handoff_closure(), closure_run_path)
    write_finance_live_handoff_preflight_report(preflight_finance_approval_live_handoff(), preflight_path)
    write_finance_approval_handoff_packet(produce_finance_approval_handoff_packet(), packet_path)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    for artifact in packet["artifacts"]:
        if artifact["name"] == "live_handoff_closure_run":
            artifact["path"] = str(closure_run_path)
        if artifact["name"] == "live_handoff_preflight":
            artifact["path"] = str(preflight_path)
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    return closure_run_path, preflight_path, packet_path
