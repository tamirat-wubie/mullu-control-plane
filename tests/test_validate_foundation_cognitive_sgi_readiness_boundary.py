"""Tests for the Foundation Mode cognitive SGI readiness boundary validator.

Purpose: prove cognitive SGI readiness preparation stays local,
read/simulation-only, deterministic, and blocked from achieved-SGI,
consciousness, production, customer, authority, deployment, or unrestricted
self-modification claims.
Governance scope: Foundation Mode, cognitive SGI readiness surfaces,
private-value exclusion, ontology-promotion blocking, external-effect blocking,
and readiness-claim blocking.
Dependencies: scripts.validate_foundation_cognitive_sgi_readiness_boundary.
Invariants: readiness surfaces remain AwaitingEvidence and reject promotion,
authority, deployment, and private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_cognitive_sgi_readiness_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_cognitive_sgi_readiness_boundary,
    validate_packet,
)


def test_foundation_cognitive_sgi_readiness_boundary_artifacts_pass() -> None:
    assert validate_foundation_cognitive_sgi_readiness_boundary() == []


def test_cognitive_sgi_readiness_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cognitive SGI readiness witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["cognitive_sgi_readiness_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["status"] == "AwaitingEvidence"
    assert payload["solver_outcome"] == "AwaitingEvidence"
    assert payload["max_candidate_level"] == "Level 4 Candidate"
    assert payload["achieved_sgi_claimed"] is False
    assert payload["autonomous_consciousness_claimed"] is False
    assert payload["production_readiness_claimed"] is False
    assert payload["external_effects_allowed"] is False
    assert payload["ontology_promotion_allowed"] is False
    assert payload["unrestricted_self_modification_claimed"] is False


def test_witness_rejects_achieved_sgi_and_consciousness_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cognitive SGI readiness witness")
    candidate = deepcopy(payload)
    candidate["achieved_sgi_claimed"] = True
    candidate["autonomous_consciousness_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cognitive_sgi_readiness_root_value_invalid" for finding in findings)
    assert not any(finding.rule_id == "cognitive_sgi_readiness_surface_state_invalid" for finding in findings)


def test_witness_rejects_production_customer_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cognitive SGI readiness witness")
    candidate = deepcopy(payload)
    candidate["production_readiness_claimed"] = True
    candidate["customer_readiness_claimed"] = True
    candidate["public_deployment_readiness_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cognitive_sgi_readiness_root_value_invalid" for finding in findings)
    assert candidate["production_readiness_claimed"] is True
    assert candidate["customer_readiness_claimed"] is True


def test_witness_rejects_external_effect_and_ontology_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cognitive SGI readiness witness")
    candidate = deepcopy(payload)
    candidate["external_effects_allowed"] = True
    candidate["ontology_promotion_allowed"] = True
    candidate["production_mutation_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cognitive_sgi_readiness_root_value_invalid" for finding in findings)
    assert candidate["external_effects_allowed"] is True
    assert candidate["ontology_promotion_allowed"] is True


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cognitive SGI readiness witness")
    candidate = deepcopy(payload)
    candidate["cognitive_sgi_readiness_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cognitive_sgi_readiness_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "cognitive_sgi_readiness_surface_state_invalid" for finding in findings)


def test_witness_rejects_endpoint_or_secret_values() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cognitive SGI readiness witness")
    candidate = deepcopy(payload)
    candidate["cognitive_sgi_readiness_surfaces"][0]["public_safe_note"] = "endpoint_url=private secret=value"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cognitive_sgi_readiness_forbidden_private_value_pattern" for finding in findings)
    assert not any(finding.rule_id == "cognitive_sgi_readiness_root_value_invalid" for finding in findings)


def test_witness_rejects_sgi_readiness_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "cognitive SGI readiness witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "SGI is achieved and deployment is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "cognitive_sgi_readiness_forbidden_promotion_phrase" for finding in findings)
    assert any(finding.rule_id == "cognitive_sgi_readiness_next_action_invalid" for finding in findings)
