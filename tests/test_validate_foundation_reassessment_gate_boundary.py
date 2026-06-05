"""Tests for the Foundation Mode reassessment gate validator.

Purpose: prove reassessment stays local and does not authorize approval,
prerequisite promotion, deployment start, pilot start, external action,
customer access, personal-data collection, legal clearance, company formation,
patent claims, money movement, secrets, publication, or deployment.
Governance scope: Foundation Mode, reassessment gate, local next-prerequisite
selection, private-value exclusion, legal/business restraint, money blocking,
secret exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_reassessment_gate_boundary.
Invariants: reassessment surfaces remain AwaitingEvidence and reject private
value drift, approval drift, and promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_reassessment_gate_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_DOC_SURFACE_LABELS,
    EXPECTED_NEXT_ACTION,
    EXPECTED_SURFACE_NOTES,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    load_text,
    validate_doc_text,
    validate_foundation_reassessment_gate_boundary,
    validate_packet,
)


def test_foundation_reassessment_gate_boundary_artifacts_pass() -> None:
    assert validate_foundation_reassessment_gate_boundary() == []


def test_reassessment_gate_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "reassessment gate witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["reassessment_approved"] is False
    assert payload["prerequisite_promotion_allowed"] is False
    assert payload["deployment_start_allowed"] is False
    assert payload["pilot_start_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["next_action"] == EXPECTED_NEXT_ACTION
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_witness_rejects_approval_and_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "reassessment gate witness")
    candidate = deepcopy(payload)
    candidate["reassessment_approved"] = True
    candidate["prerequisite_promotion_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "reassessment_gate_root_value_invalid" for finding in findings)


def test_witness_rejects_deployment_pilot_and_external_action() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "reassessment gate witness")
    candidate = deepcopy(payload)
    candidate["deployment_start_allowed"] = True
    candidate["pilot_start_allowed"] = True
    candidate["external_action_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "reassessment_gate_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_legal_company_patent_money_and_secret_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "reassessment gate witness")
    candidate = deepcopy(payload)
    candidate["customer_access_allowed"] = True
    candidate["personal_data_collection_allowed"] = True
    candidate["legal_clearance_claimed"] = True
    candidate["company_formation_claimed"] = True
    candidate["patent_claimed"] = True
    candidate["money_movement_allowed"] = True
    candidate["secret_material_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "reassessment_gate_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "reassessment gate witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "reassessment_gate_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "reassessment_gate_surface_state_invalid" for finding in findings)


def test_witness_rejects_weakened_surface_note() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "reassessment gate witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "Deployment-start question exists."

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "reassessment_gate_surface_note_invalid" for finding in findings)


def test_witness_rejects_private_or_payment_value_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "reassessment gate witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "customer_email=person@example.com; payment_id=private-value"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "reassessment_gate_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_approval_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "reassessment gate witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "deployment can start after reassessment"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "reassessment_gate_forbidden_promotion_phrase" for finding in findings)


def test_witness_rejects_extra_next_action_text() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "reassessment gate witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = f"{EXPECTED_NEXT_ACTION}; then invite pilot participants"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "reassessment_gate_next_action_invalid" for finding in findings)


def test_doc_rejects_private_or_payment_value_shape() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "reassessment gate boundary doc")
    candidate = f"{doc_text}\ncustomer_email=person@example.com\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "reassessment_gate_forbidden_value_pattern" for finding in findings)


def test_doc_requires_every_reassessment_surface_label() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "reassessment gate boundary doc")
    candidate = doc_text.replace("Rollback/recovery check", "Rollback check", 1)

    findings = validate_doc_text(candidate)

    assert "Rollback/recovery check" in EXPECTED_DOC_SURFACE_LABELS
    assert findings
    assert any(finding.rule_id == "foundation_reassessment_gate_doc_surface_missing" for finding in findings)


def test_doc_rejects_approval_promotion_phrase() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "reassessment gate boundary doc")
    candidate = f"{doc_text}\nDeployment can start after reassessment.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "reassessment_gate_forbidden_promotion_phrase" for finding in findings)
