"""Tests for the Foundation Mode documentation boundary validator.

Purpose: prove documentation preparation stays local and does not authorize
documentation-complete, canonical-docs, public-launch, customer-readiness,
deployment-readiness, legal-clearance, commercial-readiness, private-fact,
external-publication, or deployment claims.
Governance scope: Foundation Mode, documentation posture, public-copy alignment,
private-value exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_documentation_boundary.
Invariants: documentation surfaces remain AwaitingEvidence and reject readiness
promotion or private/publication drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_documentation_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_documentation_boundary,
    validate_packet,
)


def test_foundation_documentation_boundary_artifacts_pass() -> None:
    assert validate_foundation_documentation_boundary() == []


def test_documentation_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "documentation witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["documentation_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["documentation_complete_claimed"] is False
    assert payload["canonical_docs_claimed"] is False
    assert payload["public_launch_copy_claimed"] is False
    assert payload["customer_ready_copy_claimed"] is False
    assert payload["deployment_readiness_claimed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["external_publication_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_documentation_complete_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "documentation witness")
    candidate = deepcopy(payload)
    candidate["documentation_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "documentation_root_value_invalid" for finding in findings)


def test_witness_rejects_canonical_docs_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "documentation witness")
    candidate = deepcopy(payload)
    candidate["canonical_docs_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "documentation_root_value_invalid" for finding in findings)


def test_witness_rejects_external_publication_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "documentation witness")
    candidate = deepcopy(payload)
    candidate["external_publication_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "documentation_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "documentation witness")
    candidate = deepcopy(payload)
    candidate["documentation_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "documentation_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "documentation_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_path_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "documentation witness")
    candidate = deepcopy(payload)
    candidate["documentation_surfaces"][0]["public_safe_note"] = "private path=C:\\Users\\owner\\notes"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "documentation_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_documentation_complete_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "documentation witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "documentation is complete after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "documentation_forbidden_promotion_phrase" for finding in findings)
