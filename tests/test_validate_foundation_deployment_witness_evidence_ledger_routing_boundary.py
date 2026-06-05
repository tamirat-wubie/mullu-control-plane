"""Tests for the Foundation Mode deployment witness evidence ledger routing validator.

Purpose: prove issue #330 evidence ledger routing preparation stays local and
does not authorize ledger append, live evidence references, ledger promotion,
terminal closure, readiness claims, DNS proof, endpoint proof, secret-presence
claims, workflow run claims, artifact publication, deployment status approval,
operator approval, customer access, personal-data collection, money movement,
legal/business claims, publication, or deployment.
Governance scope: Foundation Mode, issue #330, deployment witness evidence
ledger routing, public-safe route labels, private-value exclusion,
external-action blocking, promotion blocking, approval blocking, and deployment
restraint.
Dependencies: scripts.validate_foundation_deployment_witness_evidence_ledger_routing_boundary.
Invariants: route surfaces remain AwaitingEvidence and reject live value drift,
ledger append drift, evidence drift, approval drift, publication drift, and
promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_deployment_witness_evidence_ledger_routing_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_DOC_SURFACE_LABELS,
    EXPECTED_NEXT_ACTION,
    EXPECTED_ROUTE_LABELS,
    EXPECTED_SURFACE_NOTES,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    load_text,
    validate_doc_text,
    validate_foundation_deployment_witness_evidence_ledger_routing_boundary,
    validate_packet,
)


def test_foundation_deployment_witness_evidence_ledger_routing_artifacts_pass() -> None:
    assert validate_foundation_deployment_witness_evidence_ledger_routing_boundary() == []


def test_evidence_ledger_routing_witness_has_expected_identity_and_surfaces() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence ledger routing witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert tuple(payload["route_labels"]) == EXPECTED_ROUTE_LABELS
    assert payload["next_action"] == EXPECTED_NEXT_ACTION
    assert payload["evidence_ledger_append_allowed"] is False
    assert payload["live_evidence_reference_allowed"] is False
    assert payload["ledger_promotion_allowed"] is False
    assert payload["readiness_claimed"] is False
    assert payload["deployment_allowed"] is False
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_doc_contains_route_labels_and_surface_labels() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness evidence ledger routing doc")

    for route_label in EXPECTED_ROUTE_LABELS:
        assert route_label in doc_text
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        assert surface_label in doc_text


def test_witness_rejects_ledger_append_live_reference_and_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence ledger routing witness")
    candidate = deepcopy(payload)
    candidate["evidence_ledger_append_allowed"] = True
    candidate["live_evidence_reference_allowed"] = True
    candidate["ledger_promotion_allowed"] = True
    candidate["terminal_closure_claimed"] = True
    candidate["readiness_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_root_value_invalid" for finding in findings)


def test_witness_rejects_dns_endpoint_secret_workflow_artifact_and_approval_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence ledger routing witness")
    candidate = deepcopy(payload)
    candidate["dns_proof_claimed"] = True
    candidate["endpoint_proof_claimed"] = True
    candidate["secret_presence_claimed"] = True
    candidate["workflow_run_claimed"] = True
    candidate["artifact_publication_allowed"] = True
    candidate["deployment_status_approval_claimed"] = True
    candidate["operator_approval_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_money_legal_company_patent_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence ledger routing witness")
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
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_root_value_invalid" for finding in findings)


def test_witness_rejects_route_label_drift() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence ledger routing witness")
    candidate = deepcopy(payload)
    candidate["route_labels"] = list(reversed(candidate["route_labels"]))

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_labels_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence ledger routing witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_evidence_ledger_routing_surface_inventory_invalid"
        for finding in findings
    )
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_surface_state_invalid" for finding in findings)


def test_witness_rejects_weakened_surface_note() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence ledger routing witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "Deployment witness route is listed."

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_surface_note_invalid" for finding in findings)


def test_witness_rejects_live_url_or_assignment_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence ledger routing witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "ledger_ref=abc123"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_ledger_approval_or_deployment_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence ledger routing witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "ledger is promoted and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_forbidden_promotion_phrase" for finding in findings)


def test_witness_rejects_extra_next_action_text() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness evidence ledger routing witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = f"{EXPECTED_NEXT_ACTION}; then append live evidence"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_next_action_invalid" for finding in findings)


def test_doc_rejects_live_url_or_assignment_shape() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness evidence ledger routing doc")
    candidate = f"{doc_text}\nledger_ref=abc123\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_forbidden_value_pattern" for finding in findings)


def test_doc_requires_every_surface_label() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness evidence ledger routing doc")
    candidate = doc_text.replace("Reassessment gate route", "Reassessment route", 1)

    findings = validate_doc_text(candidate)

    assert "Reassessment gate route" in EXPECTED_DOC_SURFACE_LABELS
    assert findings
    assert any(
        finding.rule_id == "foundation_deployment_witness_evidence_ledger_routing_doc_surface_missing"
        for finding in findings
    )


def test_doc_rejects_ledger_or_approval_promotion_phrase() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness evidence ledger routing doc")
    candidate = f"{doc_text}\nTerminal closure is complete and operator approval is complete.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_evidence_ledger_routing_forbidden_promotion_phrase" for finding in findings)
