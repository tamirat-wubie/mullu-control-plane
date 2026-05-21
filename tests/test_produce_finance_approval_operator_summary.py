"""Tests for finance approval operator summary production.

Purpose: prove packet and chain readiness collapse into a bounded operator
summary without losing promotion blockers.
Governance scope: ok/ready separation, strict promotion command preservation,
claim-boundary preservation, and schema validation.
Dependencies: scripts.produce_finance_approval_operator_summary.
Invariants:
  - Current summary is structurally valid and not promotion-ready.
  - Ready drift between packet and chain fails closed.
  - Strict promotion command remains visible to operators.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_finance_approval_operator_summary import (
    produce_finance_approval_operator_summary,
    write_finance_approval_operator_summary,
)
from scripts.validate_finance_approval_live_handoff_chain import (
    validate_finance_approval_live_handoff_chain,
    write_finance_live_handoff_chain_validation,
)
from scripts.finance_approval_handoff_test_fixtures import (
    produce_finance_handoff_packet_from_sources,
    write_finance_handoff_sources,
)


def test_finance_operator_summary_preserves_current_blocked_state(tmp_path: Path) -> None:
    packet_path, chain_path = _write_packet_and_chain(tmp_path, live_ready=False)

    summary, errors = produce_finance_approval_operator_summary(packet_path=packet_path, chain_path=chain_path)

    assert errors == ()
    assert summary["packet_ok"] is True
    assert summary["packet_ready"] is False
    assert summary["chain_ok"] is True
    assert summary["chain_ready"] is False
    assert summary["promotion_mode"] == "proof-pilot-blocked"
    assert "validate_finance_approval_live_handoff_chain.py" in summary["strict_promotion_command"]
    assert "--require-ready" in summary["strict_promotion_command"]
    assert any("finance email/calendar live receipt not ready" in blocker for blocker in summary["readiness_blockers"])
    assert summary["artifact_statuses"]["email_calendar_live_receipt"] == "blocked"
    assert summary["artifact_statuses"]["live_handoff_closure_run"] == "blocked"
    assert "live email delivery" in summary["must_not_claim"]


def test_finance_operator_summary_rejects_packet_chain_ready_drift(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    chain_path = tmp_path / "chain.json"
    packet = _packet_payload()
    chain = _chain_payload()
    chain["ready"] = True
    chain["readiness_blockers"] = []
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    chain_path.write_text(json.dumps(chain), encoding="utf-8")

    summary, errors = produce_finance_approval_operator_summary(packet_path=packet_path, chain_path=chain_path)

    assert summary["packet_ready"] is False
    assert summary["chain_ready"] is True
    assert "packet_ready and chain_ready must match" in errors


def test_finance_operator_summary_writer(tmp_path: Path) -> None:
    output_path = tmp_path / "finance_operator_summary.json"
    packet_path, chain_path = _write_packet_and_chain(tmp_path, live_ready=False)
    summary, errors = produce_finance_approval_operator_summary(packet_path=packet_path, chain_path=chain_path)

    written = write_finance_approval_operator_summary(summary, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert errors == ()
    assert written == output_path
    assert payload["summary_id"] == summary["summary_id"]
    assert payload["packet_ready"] is False


def _packet_payload() -> dict[str, object]:
    return {
        "packet_id": "finance-handoff-packet-0123456789abcdef",
        "status": "blocked",
        "ready": False,
        "promotion_boundary": {
            "ok": True,
            "ready": False,
            "mode": "proof-pilot-blocked",
            "readiness_blockers": ["finance preflight not ready"],
            "strict_promotion_command": (
                "python scripts/validate_finance_approval_live_handoff_chain.py "
                "--strict --require-ready --json"
            ),
        },
        "next_actions": ["rerun finance live handoff preflight with --strict"],
        "artifacts": [{"name": "live_handoff_closure_run", "status": "blocked"}],
        "claim_boundary": {
            "must_not_claim": [
                "live email delivery",
                "production finance automation",
            ]
        },
    }


def _write_packet_and_chain(tmp_path: Path, *, live_ready: bool) -> tuple[Path, Path]:
    paths = write_finance_handoff_sources(tmp_path, live_ready=live_ready)
    packet_path = tmp_path / "finance_handoff_packet.json"
    chain_path = tmp_path / "finance_handoff_chain.json"
    packet_path.write_text(json.dumps(produce_finance_handoff_packet_from_sources(paths)), encoding="utf-8")
    chain = validate_finance_approval_live_handoff_chain(
        closure_run_path=paths["closure_run"],
        live_receipt_path=paths["live_receipt"],
        preflight_path=paths["preflight"],
        packet_path=packet_path,
    )
    write_finance_live_handoff_chain_validation(chain, chain_path)
    return packet_path, chain_path


def _chain_payload() -> dict[str, object]:
    return {
        "ok": True,
        "ready": False,
        "readiness_blockers": ["finance preflight not ready: blocker_count=2"],
    }
