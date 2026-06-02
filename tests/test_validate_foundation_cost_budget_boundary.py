"""Tests for the Foundation Mode cost/budget boundary validator.

Purpose: prove cost/budget preparation stays local and does not authorize
spending, paid infrastructure, provider billing, payment-method binding,
subscription creation, purchase approval, invoice payment, vendor commitment,
or deployment claims.
Governance scope: Foundation Mode, cost posture, budget posture, public-safe
planning witness, payment-value exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_cost_budget_boundary.
Invariants: cost/budget surfaces remain AwaitingEvidence and reject readiness
promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_cost_budget_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_cost_budget_boundary,
    validate_packet,
)


def test_foundation_cost_budget_boundary_artifacts_pass() -> None:
    assert validate_foundation_cost_budget_boundary() == []


def test_cost_budget_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cost/budget witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["cost_budget_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["spending_allowed"] is False
    assert payload["paid_infrastructure_allowed"] is False
    assert payload["provider_billing_allowed"] is False
    assert payload["payment_method_binding_allowed"] is False
    assert payload["invoice_payment_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_spending_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cost/budget witness")
    candidate = deepcopy(payload)
    candidate["spending_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cost_budget_root_value_invalid" for finding in findings)


def test_witness_rejects_paid_infrastructure_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cost/budget witness")
    candidate = deepcopy(payload)
    candidate["paid_infrastructure_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cost_budget_root_value_invalid" for finding in findings)


def test_witness_rejects_payment_method_binding_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cost/budget witness")
    candidate = deepcopy(payload)
    candidate["payment_method_binding_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cost_budget_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cost/budget witness")
    candidate = deepcopy(payload)
    candidate["cost_budget_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cost_budget_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "cost_budget_surface_state_invalid" for finding in findings)


def test_witness_rejects_currency_amount() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cost/budget witness")
    candidate = deepcopy(payload)
    candidate["cost_budget_surfaces"][0]["public_safe_note"] = "draft quote $12"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cost_budget_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_budget_approved_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cost/budget witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "budget approved after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cost_budget_forbidden_promotion_phrase" for finding in findings)
