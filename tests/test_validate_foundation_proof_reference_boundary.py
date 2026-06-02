"""Tests for the Foundation Mode proof-reference boundary validator.

Purpose: prove proof-reference preparation stays local and does not authorize
reference completeness, proof coverage closure, evidence promotion, terminal
closure, verification pass, proof approval, runtime readiness, owner approval,
test pass, refactor approval, implementation approval, external publication,
or deployment.
Governance scope: Foundation Mode, proof-reference surface inventory,
private-value exclusion, and readiness blocking.
Dependencies: scripts.validate_foundation_proof_reference_boundary.
Invariants: proof-reference surfaces remain AwaitingEvidence and reject
readiness promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_proof_reference_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_proof_reference_boundary,
    validate_packet,
)


def test_foundation_proof_reference_boundary_artifacts_pass() -> None:
    assert validate_foundation_proof_reference_boundary() == []


def test_proof_reference_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "proof-reference witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["proof_reference_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["proof_reference_complete_claimed"] is False
    assert payload["proof_coverage_closed_claimed"] is False
    assert payload["evidence_promotion_allowed"] is False
    assert payload["terminal_closure_claimed"] is False
    assert payload["verification_pass_claimed"] is False
    assert payload["proof_approval_assigned"] is False
    assert payload["runtime_proof_ready_claimed"] is False
    assert payload["implementation_approval_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_proof_reference_completeness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "proof-reference witness")
    candidate = deepcopy(payload)
    candidate["proof_reference_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "proof_reference_root_value_invalid" for finding in findings)


def test_witness_rejects_coverage_evidence_and_terminal_closure() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "proof-reference witness")
    candidate = deepcopy(payload)
    candidate["proof_coverage_closed_claimed"] = True
    candidate["evidence_promotion_allowed"] = True
    candidate["terminal_closure_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "proof_reference_root_value_invalid" for finding in findings)


def test_witness_rejects_verification_runtime_test_and_implementation_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "proof-reference witness")
    candidate = deepcopy(payload)
    candidate["verification_pass_claimed"] = True
    candidate["runtime_proof_ready_claimed"] = True
    candidate["test_pass_claimed"] = True
    candidate["implementation_approval_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "proof_reference_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "proof-reference witness")
    candidate = deepcopy(payload)
    candidate["proof_reference_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "proof_reference_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "proof_reference_surface_state_invalid" for finding in findings)


def test_witness_rejects_proof_secret_evidence_or_test_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "proof-reference witness")
    candidate = deepcopy(payload)
    candidate["proof_reference_surfaces"][0]["public_safe_note"] = (
        "proof_id=private secret=value evidence_status=promoted test_pass=true"
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "proof_reference_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_proof_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "proof-reference witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "proof reference is complete and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "proof_reference_forbidden_promotion_phrase" for finding in findings)
