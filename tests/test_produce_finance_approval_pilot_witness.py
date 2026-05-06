"""Purpose: tests for deterministic finance approval pilot witness production.
Governance scope: blocked path, successful path, proof export, and claim
boundary preservation.
Dependencies: scripts.produce_finance_approval_pilot_witness.
Invariants:
  - Blocked path has no effect refs.
  - Successful path has approval/effect/closure refs.
  - Witness forbids live email/payment claims.
"""

from __future__ import annotations

import json

from scripts.produce_finance_approval_pilot_witness import produce_finance_approval_pilot_witness, main


def test_finance_approval_pilot_witness_contains_blocked_and_success_paths() -> None:
    witness = produce_finance_approval_pilot_witness()

    assert witness["status"] == "passed"
    assert witness["blockers"] == []
    assert witness["blocked_path"]["case"]["state"] == "requires_review"
    assert witness["blocked_path"]["case"]["effect_refs"] == []
    assert "budget_exceeded_actor_limit" in witness["blocked_path"]["policy_decision"]["reasons"]
    assert witness["successful_path"]["case"]["state"] == "closed_sent"
    assert witness["successful_path"]["case"]["approval_refs"] == ["approval-success-001"]
    assert witness["successful_path"]["case"]["effect_refs"] == ["effect-email-handoff-001"]
    assert witness["successful_path"]["proof"]["closure_certificate_id"] == "closure:case-success-001:sent"
    assert witness["external_readiness"]["readiness_level"] == "proof-pilot-ready"
    assert "email calendar evidence closed" in witness["external_readiness"]["blockers"]
    assert "live email delivery" in witness["claim_boundary"]["must_not_claim"]
    assert "autonomous payment execution" in witness["claim_boundary"]["must_not_claim"]


def test_finance_approval_pilot_witness_cli_writes_output(tmp_path, monkeypatch) -> None:
    output = tmp_path / "finance_witness.json"
    monkeypatch.setattr(
        "sys.argv",
        ["produce_finance_approval_pilot_witness.py", "--output", str(output)],
    )

    exit_code = main()
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output.exists()
    assert payload["status"] == "passed"
    assert payload["store_summary"]["case_count"] == 2
    assert payload["external_readiness"]["ready"] is False
