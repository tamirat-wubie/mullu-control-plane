"""Tests for finance approval handoff packet production.

Purpose: prove finance proof-pilot artifacts are aggregated into one bounded
operator handoff packet without executing live effects.
Governance scope: witness preservation, handoff plan references, preflight
blockers, readiness blockers, and claim-boundary integrity.
Dependencies: scripts.produce_finance_approval_handoff_packet.
Invariants:
  - Current local packet is blocked until email/calendar evidence closes.
  - Missing artifacts remain explicit blockers.
  - Must-not-claim boundaries are preserved from the witness.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_finance_approval_handoff_packet import (
    main,
    produce_finance_approval_handoff_packet,
    write_finance_approval_handoff_packet,
)


def test_current_finance_handoff_packet_preserves_blockers_and_claim_boundary() -> None:
    packet = produce_finance_approval_handoff_packet()

    assert packet["status"] == "blocked"
    assert packet["ready"] is False
    assert packet["readiness_level"] == "proof-pilot-ready"
    assert "finance email/calendar binding receipt ready" in packet["blockers"]
    assert "email calendar evidence closed" in packet["blockers"]
    assert packet["proof_summary"]["witness_status"] == "passed"
    assert packet["proof_summary"]["blocked_case_state"] == "requires_review"
    assert packet["proof_summary"]["successful_case_state"] == "closed_sent"
    assert "live email delivery" in packet["claim_boundary"]["must_not_claim"]
    assert "production finance automation" in packet["claim_boundary"]["must_not_claim"]


def test_finance_handoff_packet_reports_missing_artifacts(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"
    packet = produce_finance_approval_handoff_packet(
        witness_path=missing_path,
        handoff_plan_path=missing_path,
        binding_receipt_path=missing_path,
        closure_run_path=missing_path,
        preflight_path=missing_path,
        adapter_evidence_path=missing_path,
    )

    assert packet["status"] == "blocked"
    assert "pilot_witness_missing" in packet["blockers"]
    assert "live_handoff_plan_missing" in packet["blockers"]
    assert "email_calendar_binding_receipt_missing" in packet["blockers"]
    assert "live_handoff_closure_run_missing" in packet["blockers"]
    assert "live_handoff_preflight_missing" in packet["blockers"]
    assert packet["claim_boundary"]["must_not_claim"] == []


def test_finance_handoff_packet_writer_and_cli_emit_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "finance_handoff_packet.json"
    packet = produce_finance_approval_handoff_packet()

    written = write_finance_approval_handoff_packet(packet, output_path)
    exit_code = main(["--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 2
    assert payload["packet_id"] == stdout_payload["packet_id"]
    assert payload["status"] == "blocked"
    assert payload["artifacts"][0]["name"] == "pilot_witness"
    assert {artifact["name"] for artifact in payload["artifacts"]} == {
        "pilot_witness",
        "live_handoff_plan",
        "email_calendar_binding_receipt",
        "live_handoff_closure_run",
        "live_handoff_preflight",
    }
