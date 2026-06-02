"""Tests for the Foundation Mode research-notebook boundary validator.

Purpose: prove research-notebook preparation stays local and does not authorize
patent-protection, trade-secret-protection, scientific-validation,
physical-world-validation, market-validation, customer, publication,
paid-launch, secret-evidence, or deployment claims.
Governance scope: Foundation Mode, concept notes, assumption register,
proof-status mapping, authorship lineage, private-value exclusion, and
deployment blocking.
Dependencies: scripts.validate_foundation_research_notebook_boundary.
Invariants: research surfaces remain AwaitingEvidence and reject promotion or
private claim drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_research_notebook_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_research_notebook_boundary,
    validate_packet,
)


def test_foundation_research_notebook_boundary_artifacts_pass() -> None:
    assert validate_foundation_research_notebook_boundary() == []


def test_research_notebook_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "research-notebook witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["research_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["patent_protection_claimed"] is False
    assert payload["trade_secret_protection_claimed"] is False
    assert payload["scientific_validation_claimed"] is False
    assert payload["physical_world_validation_claimed"] is False
    assert payload["market_validation_claimed"] is False
    assert payload["customer_claim_allowed"] is False
    assert payload["secret_evidence_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_patent_protection_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "research-notebook witness")
    candidate = deepcopy(payload)
    candidate["patent_protection_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "research_notebook_root_value_invalid" for finding in findings)


def test_witness_rejects_trade_secret_protection_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "research-notebook witness")
    candidate = deepcopy(payload)
    candidate["trade_secret_protection_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "research_notebook_root_value_invalid" for finding in findings)


def test_witness_rejects_scientific_validation_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "research-notebook witness")
    candidate = deepcopy(payload)
    candidate["scientific_validation_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "research_notebook_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "research-notebook witness")
    candidate = deepcopy(payload)
    candidate["research_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "research_notebook_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "research_notebook_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_path_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "research-notebook witness")
    candidate = deepcopy(payload)
    candidate["research_surfaces"][0]["public_safe_note"] = "private note at C:\\private\\research"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "research_notebook_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_research_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "research-notebook witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "research is validated and publication ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "research_notebook_forbidden_promotion_phrase" for finding in findings)
