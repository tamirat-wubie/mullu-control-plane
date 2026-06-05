"""Tests for the Foundation Mode deployment witness evidence handoff validator.

Purpose: prove issue #330 evidence handoff preparation stays local and does
not authorize live receipts, live URL values, DNS proof, endpoint proof,
secret-presence claims, repository variable binding, workflow run claims,
artifact publication, deployment status approval, operator approval, customer
access, personal-data collection, money movement, legal/business claims,
publication, or deployment.
Governance scope: Foundation Mode, issue #330, deployment witness evidence
handoff, public-safe slot labels, private-value exclusion, external-action
blocking, approval blocking, and deployment restraint.
Dependencies: scripts.validate_foundation_deployment_witness_evidence_handoff_boundary.
Invariants: evidence handoff slots remain AwaitingEvidence and reject live
value drift, evidence drift, approval drift, publication drift, and promotion
drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_deployment_witness_evidence_handoff_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_DOC_SURFACE_LABELS,
    EXPECTED_HANDOFF_LABELS,
    EXPECTED_NEXT_ACTION,
    EXPECTED_SURFACE_NOTES,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    load_text,
    validate_doc_text,
    validate_foundation_deployment_witness_evidence_handoff_boundary,
    validate_packet,
)


def test_foundation_deployment_witness_evidence_handoff_artifacts_pass() -> None:
    assert validate_foundation_deployment_witness_evidence_handoff_boundary() == []


def test_evidence_handoff_witness_has_expected_identity_and_surfaces() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence handoff witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert tuple(payload["evidence_handoff_labels"]) == EXPECTED_HANDOFF_LABELS
    assert payload["next_action"] == EXPECTED_NEXT_ACTION
    assert payload["live_evidence_receipt_recorded"] is False
    assert payload["dns_proof_claimed"] is False
    assert payload["endpoint_proof_claimed"] is False
    assert payload["workflow_run_claimed"] is False
    assert payload["operator_approval_claimed"] is False
    assert payload["deployment_allowed"] is False
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_doc_contains_handoff_labels_and_surface_labels() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness evidence handoff doc")

    for handoff_label in EXPECTED_HANDOFF_LABELS:
        assert handoff_label in doc_text
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        assert surface_label in doc_text


def test_witness_rejects_live_receipt_dns_endpoint_and_url_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence handoff witness")
    candidate = deepcopy(payload)
    candidate["live_evidence_receipt_recorded"] = True
    candidate["live_gateway_url_value_allowed"] = True
    candidate["dns_proof_claimed"] = True
    candidate["endpoint_proof_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_root_value_invalid" for finding in findings)


def test_witness_rejects_secret_variable_workflow_artifact_status_and_operator_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence handoff witness")
    candidate = deepcopy(payload)
    candidate["secret_presence_claimed"] = True
    candidate["repository_variable_binding_allowed"] = True
    candidate["workflow_run_claimed"] = True
    candidate["witness_artifact_publication_allowed"] = True
    candidate["deployment_status_approval_claimed"] = True
    candidate["operator_approval_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_money_legal_company_patent_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence handoff witness")
    candidate = deepcopy(payload)
    candidate["customer_access_allowed"] = True
    candidate["personal_data_collection_allowed"] = True
    candidate["money_movement_allowed"] = True
    candidate["legal_clearance_claimed"] = True
    candidate["company_formation_claimed"] = True
    candidate["patent_claimed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_root_value_invalid" for finding in findings)


def test_witness_rejects_handoff_label_drift() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence handoff witness")
    candidate = deepcopy(payload)
    candidate["evidence_handoff_labels"] = list(reversed(candidate["evidence_handoff_labels"]))

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_labels_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence handoff witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_surface_state_invalid" for finding in findings)


def test_witness_rejects_weakened_surface_note() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence handoff witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "Deployment witness receipt slot is listed."

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_surface_note_invalid" for finding in findings)


def test_witness_rejects_live_url_or_assignment_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence handoff witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "approval_id=abc123"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_evidence_approval_or_deployment_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence handoff witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "operator approval is verified and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_forbidden_promotion_phrase" for finding in findings)


def test_witness_rejects_extra_next_action_text() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence handoff witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = f"{EXPECTED_NEXT_ACTION}; then collect live receipts"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_next_action_invalid" for finding in findings)


def test_doc_rejects_live_url_or_assignment_shape() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness evidence handoff doc")
    candidate = f"{doc_text}\nreceipt_id=abc123\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_forbidden_value_pattern" for finding in findings)


def test_doc_requires_every_surface_label() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness evidence handoff doc")
    candidate = doc_text.replace("Operator decision slot", "Operator slot", 1)

    findings = validate_doc_text(candidate)

    assert "Operator decision slot" in EXPECTED_DOC_SURFACE_LABELS
    assert findings
    assert any(
        finding.rule_id == "foundation_deployment_witness_evidence_handoff_doc_surface_missing"
        for finding in findings
    )


def test_doc_rejects_evidence_or_approval_promotion_phrase() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness evidence handoff doc")
    candidate = f"{doc_text}\nDNS proof is verified and operator approval is complete.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_handoff_forbidden_promotion_phrase" for finding in findings)
