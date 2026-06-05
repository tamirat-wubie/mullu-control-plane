"""Tests for the Foundation Mode gateway endpoint evidence receipt validator.

Purpose: prove issue #330 endpoint evidence receipt-shape preparation stays
local and does not authorize endpoint probes, gateway or endpoint URL values,
HTTP status values, response evidence, timestamps, collector identities,
evidence-ledger append, witness collection, public-health declarations,
workflow dispatch, artifact publication, approval, readiness claims, customer
access, money movement, legal/business claims, publication, or deployment.
Governance scope: Foundation Mode, issue #330 endpoint evidence receipt
rehearsal, public-safe field labels, private-value exclusion, promotion
blocking, ledger append blocking, approval blocking, publication blocking,
and deployment restraint.
Dependencies: scripts.validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary.
Invariants: receipt field surfaces remain AwaitingEvidence and reject endpoint
probe drift, response-evidence drift, ledger drift, approval drift,
publication drift, and deployment drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_DOC_SURFACE_LABELS,
    EXPECTED_FIELD_LABELS,
    EXPECTED_NEXT_ACTION,
    EXPECTED_SURFACE_NOTES,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    load_text,
    validate_doc_text,
    validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary,
    validate_packet,
)


def test_foundation_gateway_endpoint_evidence_receipt_rehearsal_artifacts_pass() -> None:
    assert validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary() == []


def test_gateway_endpoint_evidence_receipt_witness_has_expected_identity_and_surfaces() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway endpoint evidence receipt rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert tuple(payload["field_labels"]) == EXPECTED_FIELD_LABELS
    assert payload["next_action"] == EXPECTED_NEXT_ACTION
    assert payload["endpoint_probe_allowed"] is False
    assert payload["gateway_url_value_allowed"] is False
    assert payload["endpoint_url_value_allowed"] is False
    assert payload["http_status_value_allowed"] is False
    assert payload["response_digest_value_allowed"] is False
    assert payload["response_body_value_allowed"] is False
    assert payload["collection_timestamp_value_allowed"] is False
    assert payload["collector_identity_value_allowed"] is False
    assert payload["evidence_ledger_append_allowed"] is False
    assert payload["deployment_witness_collection_allowed"] is False
    assert payload["public_health_declaration_allowed"] is False
    assert payload["readiness_claimed"] is False
    assert payload["deployment_allowed"] is False
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_doc_contains_field_labels_and_surface_labels() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "gateway endpoint evidence receipt rehearsal doc")

    for field_label in EXPECTED_FIELD_LABELS:
        assert field_label in doc_text
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        assert surface_label in doc_text


def test_witness_rejects_endpoint_probe_url_status_response_and_timestamp_values() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway endpoint evidence receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["endpoint_probe_allowed"] = True
    candidate["gateway_url_value_allowed"] = True
    candidate["endpoint_url_value_allowed"] = True
    candidate["http_status_value_allowed"] = True
    candidate["response_digest_value_allowed"] = True
    candidate["response_body_value_allowed"] = True
    candidate["collection_timestamp_value_allowed"] = True
    candidate["collector_identity_value_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_runtime_production_capability_audit_and_proof_payloads() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway endpoint evidence receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["runtime_witness_payload_allowed"] = True
    candidate["runtime_conformance_payload_allowed"] = True
    candidate["production_evidence_payload_allowed"] = True
    candidate["capability_evidence_payload_allowed"] = True
    candidate["audit_verification_payload_allowed"] = True
    candidate["proof_verification_payload_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_ledger_public_health_secret_workflow_artifact_and_approval_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway endpoint evidence receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["evidence_ledger_append_allowed"] = True
    candidate["deployment_witness_collection_allowed"] = True
    candidate["public_health_declaration_allowed"] = True
    candidate["secret_presence_claimed"] = True
    candidate["workflow_dispatch_allowed"] = True
    candidate["artifact_publication_allowed"] = True
    candidate["operator_approval_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_money_legal_company_patent_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway endpoint evidence receipt rehearsal witness")
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
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_field_label_drift() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway endpoint evidence receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["field_labels"] = list(reversed(candidate["field_labels"]))

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway endpoint evidence receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_surface_inventory_invalid"
        for finding in findings
    )
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_url_host_ip_timestamp_or_assignment_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway endpoint evidence receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "endpoint_url=https://gateway.example.com status=200"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_endpoint_evidence_or_deployment_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway endpoint evidence receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "endpoint evidence is verified and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_forbidden_promotion_phrase" for finding in findings)


def test_witness_rejects_extra_next_action_text() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway endpoint evidence receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = f"{EXPECTED_NEXT_ACTION}; then append evidence to a ledger"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_doc_rejects_url_host_ip_timestamp_or_assignment_shape() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "gateway endpoint evidence receipt rehearsal doc")
    candidate = f"{doc_text}\nendpoint_url=https://gateway.example.com http_status=200 checked_at=2026-06-05T10:00Z\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_forbidden_value_pattern" for finding in findings)


def test_doc_requires_every_surface_label() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "gateway endpoint evidence receipt rehearsal doc")
    candidate = doc_text.replace("Endpoint evidence ledger route slot", "Endpoint ledger slot", 1)

    findings = validate_doc_text(candidate)

    assert "Endpoint evidence ledger route slot" in EXPECTED_DOC_SURFACE_LABELS
    assert findings
    assert any(
        finding.rule_id == "foundation_gateway_endpoint_evidence_receipt_rehearsal_doc_surface_missing"
        for finding in findings
    )


def test_doc_rejects_public_health_operator_or_ledger_promotion_phrase() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "gateway endpoint evidence receipt rehearsal doc")
    candidate = f"{doc_text}\nEndpoint evidence receipt is published and operator approval is complete.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_endpoint_evidence_receipt_rehearsal_forbidden_promotion_phrase" for finding in findings)
