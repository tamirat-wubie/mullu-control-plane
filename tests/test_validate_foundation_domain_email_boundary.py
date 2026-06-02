"""Tests for the Foundation Mode domain/email boundary validator.

Purpose: prove domain and email preparation stays public-safe and does not
authorize DNS mutation, endpoint readiness, email deliverability, provider
private values, or deployment.
Governance scope: Foundation Mode, domain/email posture, public-label witness,
provider-private exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_domain_email_boundary.
Invariants: the witness keeps all public surfaces AwaitingEvidence and rejects
private target-shaped values or readiness-promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_domain_email_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_domain_email_boundary,
    validate_packet,
)


def test_foundation_domain_email_boundary_artifacts_pass() -> None:
    assert validate_foundation_domain_email_boundary() == []


def test_domain_email_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "domain/email witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["label"])
        for surface in payload["public_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["dns_mutation_allowed"] is False
    assert payload["api_dns_publication_allowed"] is False
    assert payload["endpoint_readiness_claimed"] is False
    assert payload["email_deliverability_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_dns_mutation_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "domain/email witness")
    candidate = deepcopy(payload)
    candidate["dns_mutation_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "domain_email_root_value_invalid" for finding in findings)


def test_witness_rejects_email_deliverability_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "domain/email witness")
    candidate = deepcopy(payload)
    candidate["email_deliverability_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "domain_email_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "domain/email witness")
    candidate = deepcopy(payload)
    candidate["public_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "domain_email_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_dns_target_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "domain/email witness")
    candidate = deepcopy(payload)
    candidate["public_surfaces"][0]["public_safe_note"] = "Origin target=203.0.113.10"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "domain_email_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_private_provider_field_addition() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "domain/email witness")
    candidate = deepcopy(payload)
    candidate["provider_account_id"] = "do-not-store"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "domain_email_root_keys_invalid" for finding in findings)
