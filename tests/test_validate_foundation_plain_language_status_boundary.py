"""Tests for the Foundation Mode plain-language status boundary validator.

Purpose: prove plain-language status preparation stays local and does not
authorize product readiness, capability availability, customer readiness, legal
clearance, paid use, money movement, external publication, or deployment.
Governance scope: Foundation Mode, plain-language surfaces, plain-English
overview posture, private-value exclusion, and readiness blocking.
Dependencies: scripts.validate_foundation_plain_language_status_boundary.
Invariants: plain-language surfaces remain AwaitingEvidence and reject
readiness promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_plain_language_status_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_plain_language_status_boundary,
    validate_packet,
    validate_plain_overview_text,
)


def test_foundation_plain_language_status_boundary_artifacts_pass() -> None:
    assert validate_foundation_plain_language_status_boundary() == []


def test_plain_language_status_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "plain-language status witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["plain_language_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["plain_language_complete_claimed"] is False
    assert payload["product_readiness_claimed"] is False
    assert payload["capability_availability_claimed"] is False
    assert payload["customer_readiness_claimed"] is False
    assert payload["money_movement_ready_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_plain_language_completeness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "plain-language status witness")
    candidate = deepcopy(payload)
    candidate["plain_language_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "plain_language_status_root_value_invalid" for finding in findings)


def test_witness_rejects_readiness_and_capability_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "plain-language status witness")
    candidate = deepcopy(payload)
    candidate["product_readiness_claimed"] = True
    candidate["capability_availability_claimed"] = True
    candidate["real_task_execution_ready"] = True
    candidate["customer_readiness_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "plain_language_status_root_value_invalid" for finding in findings)


def test_witness_rejects_legal_paid_money_publication_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "plain-language status witness")
    candidate = deepcopy(payload)
    candidate["legal_clearance_claimed"] = True
    candidate["paid_use_ready_claimed"] = True
    candidate["money_movement_ready_claimed"] = True
    candidate["external_publication_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "plain_language_status_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "plain-language status witness")
    candidate = deepcopy(payload)
    candidate["plain_language_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "plain_language_status_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "plain_language_status_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_customer_money_or_deployment_values() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "plain-language status witness")
    candidate = deepcopy(payload)
    candidate["plain_language_surfaces"][0]["public_safe_note"] = (
        "customer_id=abc payment_amount=12 endpoint_url=value"
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "plain_language_status_forbidden_private_value_pattern" for finding in findings)


def test_plain_overview_rejects_readiness_promotion_phrase() -> None:
    findings = validate_plain_overview_text("The product is ready and deployment is ready.")

    assert findings
    assert any(finding.rule_id == "plain_language_status_forbidden_promotion_phrase" for finding in findings)
