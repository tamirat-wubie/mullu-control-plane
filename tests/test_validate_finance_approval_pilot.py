"""Purpose: tests for finance approval pilot readiness validation.
Governance scope: proof-pilot readiness, live email blocker reporting, and
adapter evidence closure promotion.
Dependencies: scripts.validate_finance_approval_pilot and JSON fixtures.
Invariants:
  - Current repository evidence is at least proof-pilot ready.
  - Live readiness remains blocked until email/calendar evidence is closed.
  - Closed email evidence promotes readiness without changing proof artifacts.
"""

from __future__ import annotations

import json

from scripts.validate_finance_approval_pilot import validate_finance_approval_pilot


def test_current_finance_pilot_is_proof_ready_but_not_live_email_ready() -> None:
    report = validate_finance_approval_pilot()
    checks = {check["name"]: check for check in report.checks}

    assert report.readiness_level == "proof-pilot-ready"
    assert report.ready is False
    assert checks["finance proof schema present"]["passed"] is True
    assert checks["finance pilot runbook present"]["passed"] is True
    assert checks["finance routes classified"]["passed"] is True
    assert checks["document parser evidence closed"]["passed"] is True
    assert checks["email calendar evidence closed"]["passed"] is False
    assert "email calendar evidence closed" in report.blockers


def test_closed_email_calendar_evidence_promotes_live_readiness(tmp_path) -> None:
    evidence = {
        "adapters": [
            {
                "adapter_id": "document.production_parsers",
                "status": "closed",
                "blockers": [],
                "evidence_refs": ["document_live_receipt.json"],
            },
            {
                "adapter_id": "communication.email_calendar_worker",
                "status": "closed",
                "blockers": [],
                "evidence_refs": ["email_calendar_live_receipt.json"],
            },
        ]
    }
    evidence_path = tmp_path / "capability_adapter_evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    report = validate_finance_approval_pilot(adapter_evidence_path=evidence_path)

    assert report.ready is True
    assert report.readiness_level == "live-email-handoff-ready"
    assert report.blockers == ()
