"""Tests for the Foundation Mode decision-journal boundary validator.

Purpose: prove decision-journal preparation stays local and does not authorize
decision-execution, irreversible-action, roadmap-commitment, deadline-promise,
authority-delegation, customer-commitment, legal-authority, company-action,
patent-filing, spending, external-publication, or deployment claims.
Governance scope: Foundation Mode, decision context, assumption snapshot,
option set, constraint check, evidence references, risk stop rule, review
cadence, next-action selection, private-value exclusion, and commitment
blocking.
Dependencies: scripts.validate_foundation_decision_journal_boundary.
Invariants: decision surfaces remain AwaitingEvidence and reject promotion or
private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_decision_journal_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_decision_journal_boundary,
    validate_packet,
)


def test_foundation_decision_journal_boundary_artifacts_pass() -> None:
    assert validate_foundation_decision_journal_boundary() == []


def test_decision_journal_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "decision-journal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["decision_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["decision_execution_allowed"] is False
    assert payload["irreversible_action_allowed"] is False
    assert payload["roadmap_commitment_claimed"] is False
    assert payload["deadline_promise_claimed"] is False
    assert payload["customer_commitment_claimed"] is False
    assert payload["company_action_allowed"] is False
    assert payload["patent_filing_allowed"] is False
    assert payload["spending_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_decision_execution() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "decision-journal witness")
    candidate = deepcopy(payload)
    candidate["decision_execution_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "decision_journal_root_value_invalid" for finding in findings)


def test_witness_rejects_roadmap_commitment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "decision-journal witness")
    candidate = deepcopy(payload)
    candidate["roadmap_commitment_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "decision_journal_root_value_invalid" for finding in findings)


def test_witness_rejects_spending_allowance() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "decision-journal witness")
    candidate = deepcopy(payload)
    candidate["spending_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "decision_journal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "decision-journal witness")
    candidate = deepcopy(payload)
    candidate["decision_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "decision_journal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "decision_journal_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_schedule_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "decision-journal witness")
    candidate = deepcopy(payload)
    candidate["decision_surfaces"][0]["public_safe_note"] = "deadline_at=private-date"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "decision_journal_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_decision_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "decision-journal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "decision is executed and roadmap is committed"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "decision_journal_forbidden_promotion_phrase" for finding in findings)
