"""Tests for the Foundation Mode payment-provider boundary validator.

Purpose: prove payment-provider preparation stays local and does not authorize
provider activation, account binding, payment-method collection, live charges,
refunds, payouts, webhooks, checkout publication, money movement, customer
payment access, external publication, or deployment claims.
Governance scope: Foundation Mode, payment-provider posture, public-safe
planning witness, provider/private value exclusion, and money-movement blocking.
Dependencies: scripts.validate_foundation_payment_provider_boundary.
Invariants: payment-provider surfaces remain AwaitingEvidence and reject
readiness promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_payment_provider_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_payment_provider_boundary,
    validate_packet,
)


def test_foundation_payment_provider_boundary_artifacts_pass() -> None:
    assert validate_foundation_payment_provider_boundary() == []


def test_payment_provider_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "payment-provider witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["payment_provider_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["payment_provider_activation_allowed"] is False
    assert payload["provider_account_binding_allowed"] is False
    assert payload["payment_method_collection_allowed"] is False
    assert payload["live_charge_allowed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_provider_activation_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "payment-provider witness")
    candidate = deepcopy(payload)
    candidate["payment_provider_activation_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "payment_provider_root_value_invalid" for finding in findings)


def test_witness_rejects_account_binding_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "payment-provider witness")
    candidate = deepcopy(payload)
    candidate["provider_account_binding_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "payment_provider_root_value_invalid" for finding in findings)


def test_witness_rejects_money_movement_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "payment-provider witness")
    candidate = deepcopy(payload)
    candidate["money_movement_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "payment_provider_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "payment-provider witness")
    candidate = deepcopy(payload)
    candidate["payment_provider_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "payment_provider_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "payment_provider_surface_state_invalid" for finding in findings)


def test_witness_rejects_provider_identifier() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "payment-provider witness")
    candidate = deepcopy(payload)
    candidate["payment_provider_surfaces"][0]["public_safe_note"] = "acct_1234567890 is not public-safe"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "payment_provider_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_provider_active_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "payment-provider witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "payment provider is active after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "payment_provider_forbidden_promotion_phrase" for finding in findings)
