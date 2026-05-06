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


def test_finance_operator_summary_preserves_current_blocked_state() -> None:
    summary, errors = produce_finance_approval_operator_summary()

    assert errors == ()
    assert summary["packet_ok"] is True
    assert summary["packet_ready"] is False
    assert summary["chain_ok"] is True
    assert summary["chain_ready"] is False
    assert summary["promotion_mode"] == "proof-pilot-blocked"
    assert "validate_finance_approval_live_handoff_chain.py" in summary["strict_promotion_command"]
    assert "--require-ready" in summary["strict_promotion_command"]
    assert (
        "finance email/calendar live receipt not ready: status=failed "
        "blockers=['email_calendar_worker_probe_failed']"
    ) in summary["readiness_blockers"]
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
    summary, errors = produce_finance_approval_operator_summary()

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


def _chain_payload() -> dict[str, object]:
    return {
        "ok": True,
        "ready": False,
        "readiness_blockers": ["finance preflight not ready: blocker_count=2"],
    }
