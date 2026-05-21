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

from scripts.produce_finance_approval_handoff_packet import write_finance_approval_handoff_packet
from scripts.validate_finance_approval_live_handoff_chain import (
    main,
    validate_finance_approval_live_handoff_chain,
    write_finance_live_handoff_chain_validation,
)
from scripts.finance_approval_handoff_test_fixtures import (
    produce_finance_handoff_packet_from_sources,
    write_finance_handoff_sources,
)


def test_finance_live_handoff_chain_accepts_current_artifacts(tmp_path: Path) -> None:
    paths = _write_current_chain(tmp_path, live_ready=False)
    validation = _validate_chain(paths)

    assert validation.ok is True
    assert validation.ready is False
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
    assert any("finance email/calendar live receipt not ready" in blocker for blocker in validation.readiness_blockers)


def test_finance_live_handoff_chain_ready_requires_ready_live_receipt(tmp_path: Path) -> None:
    paths = _write_current_chain(tmp_path, live_ready=True)

    validation = _validate_chain(paths)

    assert validation.ok is True
    assert validation.ready is True
    assert validation.blockers == ()
    assert validation.readiness_blockers == ()


def test_finance_live_handoff_chain_rejects_invalid_closure_run(tmp_path: Path) -> None:
    paths = _write_current_chain(tmp_path, live_ready=False)
    closure_run_path = paths["closure_run"]
    closure_run = json.loads(closure_run_path.read_text(encoding="utf-8"))
    closure_run["commands"] = []
    closure_run["command_count"] = 0
    closure_run_path.write_text(json.dumps(closure_run), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_chain(
        closure_run_path=closure_run_path,
        live_receipt_path=paths["live_receipt"],
        preflight_path=paths["preflight"],
        packet_path=paths["packet"],
    )

    assert validation.ok is False
    assert "finance closure run schema validation" in validation.blockers


def test_finance_live_handoff_chain_rejects_invalid_preflight(tmp_path: Path) -> None:
    paths = _write_current_chain(tmp_path, live_ready=False)
    preflight = json.loads(paths["preflight"].read_text(encoding="utf-8"))
    preflight["blockers"] = []
    paths["preflight"].write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_chain(
        closure_run_path=paths["closure_run"],
        live_receipt_path=paths["live_receipt"],
        preflight_path=paths["preflight"],
        packet_path=paths["packet"],
    )

    assert validation.ok is False
    assert "finance preflight schema validation" in validation.blockers
    assert "finance handoff packet schema validation" in validation.blockers


def test_finance_live_handoff_chain_rejects_invalid_live_receipt(tmp_path: Path) -> None:
    paths = _write_current_chain(tmp_path, live_ready=False)
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
        closure_run_path=paths["closure_run"],
        live_receipt_path=live_receipt_path,
        preflight_path=paths["preflight"],
        packet_path=paths["packet"],
    )

    assert validation.ok is False
    assert "finance email/calendar live receipt validation" in validation.blockers


def test_finance_live_handoff_chain_rejects_packet_live_receipt_path_mismatch(tmp_path: Path) -> None:
    paths = _write_current_chain(tmp_path, live_ready=True)
    mismatched_live_receipt_path = tmp_path / "mismatched_live_receipt.json"
    mismatched_live_receipt_path.write_text(paths["live_receipt"].read_text(encoding="utf-8"), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_chain(
        closure_run_path=paths["closure_run"],
        live_receipt_path=mismatched_live_receipt_path,
        preflight_path=paths["preflight"],
        packet_path=paths["packet"],
    )

    assert validation.ok is False
    assert "finance handoff packet schema validation" in validation.blockers


def test_finance_live_handoff_chain_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    paths = _write_current_chain(tmp_path, live_ready=False)
    output_path = tmp_path / "chain_validation.json"
    closure_run = json.loads(paths["closure_run"].read_text(encoding="utf-8"))
    closure_run["status"] = "ready"
    paths["closure_run"].write_text(json.dumps(closure_run), encoding="utf-8")
    validation = validate_finance_approval_live_handoff_chain(
        closure_run_path=paths["closure_run"],
        live_receipt_path=paths["live_receipt"],
        preflight_path=paths["preflight"],
        packet_path=paths["packet"],
    )

    written = write_finance_live_handoff_chain_validation(validation, output_path)
    exit_code = main(
        [
            "--closure-run",
            str(paths["closure_run"]),
            "--live-receipt",
            str(paths["live_receipt"]),
            "--preflight",
            str(paths["preflight"]),
            "--packet",
            str(paths["packet"]),
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


def _write_current_chain(tmp_path: Path, *, live_ready: bool) -> dict[str, Path]:
    paths = write_finance_handoff_sources(tmp_path, live_ready=live_ready)
    packet_path = tmp_path / "finance_handoff_packet.json"
    write_finance_approval_handoff_packet(produce_finance_handoff_packet_from_sources(paths), packet_path)
    return paths | {"packet": packet_path}


def _validate_chain(paths: dict[str, Path]):
    return validate_finance_approval_live_handoff_chain(
        closure_run_path=paths["closure_run"],
        live_receipt_path=paths["live_receipt"],
        preflight_path=paths["preflight"],
        packet_path=paths["packet"],
    )
