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
from scripts.finance_approval_handoff_test_fixtures import (
    produce_finance_handoff_packet_from_sources,
    write_finance_handoff_sources,
)


def test_current_finance_handoff_packet_preserves_blockers_and_claim_boundary(tmp_path: Path) -> None:
    paths = write_finance_handoff_sources(tmp_path, live_ready=False)
    packet = produce_finance_handoff_packet_from_sources(paths)

    assert packet["status"] == "blocked"
    assert packet["ready"] is False
    assert packet["promotion_boundary"]["ok"] is True
    assert packet["promotion_boundary"]["ready"] is False
    assert packet["promotion_boundary"]["mode"] == "proof-pilot-blocked"
    assert "validate_finance_approval_live_handoff_chain.py" in packet["promotion_boundary"]["strict_promotion_command"]
    assert packet["promotion_boundary"]["readiness_blockers"]
    assert packet["readiness_level"] in {"not-ready", "proof-pilot-ready"}
    assert "email_calendar_live_receipt_not_ready" in packet["blockers"]
    assert "email_calendar_probe_exception" in packet["blockers"]
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
    assert packet["promotion_boundary"]["ok"] is False
    assert packet["promotion_boundary"]["ready"] is False
    assert "pilot_witness_missing" in packet["blockers"]
    assert "live_handoff_plan_missing" in packet["blockers"]
    assert "email_calendar_binding_receipt_missing" in packet["blockers"]
    assert "email_calendar_live_receipt_missing" in packet["blockers"]
    assert "live_handoff_closure_run_missing" in packet["blockers"]
    assert "live_handoff_preflight_missing" in packet["blockers"]
    assert packet["claim_boundary"]["must_not_claim"] == []


def test_finance_handoff_packet_writer_and_cli_emit_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "finance_handoff_packet.json"
    paths = write_finance_handoff_sources(tmp_path, live_ready=False)
    packet = produce_finance_handoff_packet_from_sources(paths)

    written = write_finance_approval_handoff_packet(packet, output_path)
    exit_code = main(
        [
            "--witness",
            str(paths["witness"]),
            "--handoff-plan",
            str(paths["handoff_plan"]),
            "--binding-receipt",
            str(paths["binding_receipt"]),
            "--live-receipt",
            str(paths["live_receipt"]),
            "--closure-run",
            str(paths["closure_run"]),
            "--preflight",
            str(paths["preflight"]),
            "--adapter-evidence",
            str(paths["adapter_evidence"]),
            "--output",
            str(output_path),
            "--json",
        ]
    )
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
        "email_calendar_live_receipt",
        "live_handoff_closure_run",
        "live_handoff_preflight",
    }


def test_finance_handoff_packet_requires_ready_live_receipt(tmp_path: Path) -> None:
    blocked_paths = write_finance_handoff_sources(tmp_path / "blocked", live_ready=False)
    ready_paths = write_finance_handoff_sources(tmp_path / "ready", live_ready=True)

    blocked_packet = produce_finance_handoff_packet_from_sources(blocked_paths)
    ready_packet = produce_finance_handoff_packet_from_sources(ready_paths)

    assert blocked_packet["ready"] is False
    assert "email_calendar_live_receipt_not_ready" in blocked_packet["blockers"]
    assert _artifact_status(blocked_packet, "email_calendar_live_receipt") == "blocked"
    assert ready_packet["ready"] is True
    assert ready_packet["status"] == "ready"
    assert ready_packet["blockers"] == []
    assert _artifact_status(ready_packet, "email_calendar_live_receipt") == "ready"


def _artifact_status(packet: dict[str, object], artifact_name: str) -> str:
    artifacts = packet["artifacts"]
    assert isinstance(artifacts, list)
    for artifact in artifacts:
        assert isinstance(artifact, dict)
        if artifact["name"] == artifact_name:
            return str(artifact["status"])
    raise AssertionError(f"missing artifact {artifact_name}")
