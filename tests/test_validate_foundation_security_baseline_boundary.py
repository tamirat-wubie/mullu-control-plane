"""Tests for the Foundation Mode security-baseline boundary validator.

Purpose: prove security-baseline preparation stays local and does not authorize
scan-pass, dependency-audit pass, threat-model approval, access-control
verification, data-exposure approval, supply-chain approval, compliance,
customer-security, or deployment claims.
Governance scope: Foundation Mode, local security posture, public-safe planning
witness, private-value exclusion, security-readiness blocking, and deployment
blocking.
Dependencies: scripts.validate_foundation_security_baseline_boundary.
Invariants: security-baseline surfaces remain AwaitingEvidence and reject
readiness promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_security_baseline_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_security_baseline_boundary,
    validate_packet,
)


def test_foundation_security_baseline_boundary_artifacts_pass() -> None:
    assert validate_foundation_security_baseline_boundary() == []


def test_security_baseline_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "security-baseline witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["security_baseline_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["security_baseline_verified"] is False
    assert payload["secret_scan_pass_claimed"] is False
    assert payload["vulnerability_scan_pass_claimed"] is False
    assert payload["dependency_audit_pass_claimed"] is False
    assert payload["compliance_certification_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_security_baseline_verification_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "security-baseline witness")
    candidate = deepcopy(payload)
    candidate["security_baseline_verified"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "security_baseline_root_value_invalid" for finding in findings)


def test_witness_rejects_scan_pass_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "security-baseline witness")
    candidate = deepcopy(payload)
    candidate["secret_scan_pass_claimed"] = True
    candidate["vulnerability_scan_pass_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "security_baseline_root_value_invalid" for finding in findings)


def test_witness_rejects_threat_model_and_compliance_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "security-baseline witness")
    candidate = deepcopy(payload)
    candidate["threat_model_approved"] = True
    candidate["compliance_certification_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "security_baseline_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "security-baseline witness")
    candidate = deepcopy(payload)
    candidate["security_baseline_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "security_baseline_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "security_baseline_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_scan_target_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "security-baseline witness")
    candidate = deepcopy(payload)
    candidate["security_baseline_surfaces"][0]["public_safe_note"] = "scan_target=C:\\private\\repo"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "security_baseline_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_security_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "security-baseline witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "security is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "security_baseline_forbidden_promotion_phrase" for finding in findings)
