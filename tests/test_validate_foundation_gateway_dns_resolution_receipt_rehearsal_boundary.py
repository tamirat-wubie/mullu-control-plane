"""Tests for the Foundation Mode gateway DNS resolution receipt rehearsal validator.

Purpose: prove issue #330 DNS resolution receipt preparation stays local and
does not authorize live DNS queries, host values, gateway URL values, resolved
addresses, resolver-error proof, DNS proof, receipt writing, endpoint proof,
repository-variable binding, secret-presence claims, workflow dispatch,
artifact publication, operator approval, readiness claims, customer access,
personal-data collection, money movement, legal/business claims, publication,
or deployment.
Governance scope: Foundation Mode, issue #330, gateway DNS resolution receipt
rehearsal, public-safe question labels, private-value exclusion,
external-action blocking, promotion blocking, approval blocking, and deployment
restraint.
Dependencies: scripts.validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary.
Invariants: rehearsal surfaces remain AwaitingEvidence and reject live DNS
drift, host/address drift, receipt-writing drift, approval drift, publication
drift, and deployment drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_DOC_SURFACE_LABELS,
    EXPECTED_NEXT_ACTION,
    EXPECTED_QUESTION_LABELS,
    EXPECTED_SURFACE_NOTES,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    load_text,
    validate_doc_text,
    validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary,
    validate_packet,
)


def test_foundation_gateway_dns_resolution_receipt_rehearsal_artifacts_pass() -> None:
    assert validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary() == []


def test_gateway_dns_resolution_receipt_rehearsal_witness_has_expected_identity_and_surfaces() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS resolution receipt rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert tuple(payload["question_labels"]) == EXPECTED_QUESTION_LABELS
    assert payload["next_action"] == EXPECTED_NEXT_ACTION
    assert payload["live_dns_query_allowed"] is False
    assert payload["host_value_recorded"] is False
    assert payload["resolved_address_recorded"] is False
    assert payload["dns_resolution_claimed"] is False
    assert payload["dns_receipt_written"] is False
    assert payload["readiness_claimed"] is False
    assert payload["deployment_allowed"] is False
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_doc_contains_question_labels_and_surface_labels() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "gateway DNS resolution receipt rehearsal doc")

    for question_label in EXPECTED_QUESTION_LABELS:
        assert question_label in doc_text
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        assert surface_label in doc_text


def test_witness_rejects_dns_host_gateway_address_and_receipt_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS resolution receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["live_dns_query_allowed"] = True
    candidate["host_value_recorded"] = True
    candidate["gateway_url_recorded"] = True
    candidate["resolved_address_recorded"] = True
    candidate["dns_receipt_written"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_dns_endpoint_secret_workflow_artifact_and_approval_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS resolution receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["resolver_error_proof_claimed"] = True
    candidate["dns_resolution_claimed"] = True
    candidate["endpoint_reachability_claimed"] = True
    candidate["secret_presence_claimed"] = True
    candidate["workflow_dispatch_allowed"] = True
    candidate["artifact_publication_allowed"] = True
    candidate["operator_approval_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_money_legal_company_patent_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS resolution receipt rehearsal witness")
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
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_question_label_drift() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS resolution receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["question_labels"] = list(reversed(candidate["question_labels"]))

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS resolution receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_surface_inventory_invalid"
        for finding in findings
    )
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_weakened_surface_note() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS resolution receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "DNS query can be run later."

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_surface_note_invalid" for finding in findings)


def test_witness_rejects_live_url_host_ip_timestamp_or_assignment_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS resolution receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "dns_host=gateway.example.com resolved_address=192.0.2.1"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_dns_receipt_or_deployment_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS resolution receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "dns receipt is written and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_forbidden_promotion_phrase" for finding in findings)


def test_witness_rejects_extra_next_action_text() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS resolution receipt rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = f"{EXPECTED_NEXT_ACTION}; then run live DNS query"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_root_value_invalid" for finding in findings)


def test_doc_rejects_live_url_host_ip_timestamp_or_assignment_shape() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "gateway DNS resolution receipt rehearsal doc")
    candidate = f"{doc_text}\ndns_host=gateway.example.com resolved_address=192.0.2.1 checked_at=2026-06-05T10:00Z\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_forbidden_value_pattern" for finding in findings)


def test_doc_requires_every_surface_label() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "gateway DNS resolution receipt rehearsal doc")
    candidate = doc_text.replace("TTL observation question", "TTL question", 1)

    findings = validate_doc_text(candidate)

    assert "TTL observation question" in EXPECTED_DOC_SURFACE_LABELS
    assert findings
    assert any(
        finding.rule_id == "foundation_gateway_dns_resolution_receipt_rehearsal_doc_surface_missing"
        for finding in findings
    )


def test_doc_rejects_dns_resolution_or_operator_promotion_phrase() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "gateway DNS resolution receipt rehearsal doc")
    candidate = f"{doc_text}\nDNS resolution is verified and operator approval is complete.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_resolution_receipt_rehearsal_forbidden_promotion_phrase" for finding in findings)
