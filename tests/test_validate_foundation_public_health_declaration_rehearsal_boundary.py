"""Tests for the Foundation Mode public health declaration rehearsal validator.

Purpose: prove issue #330 public health declaration preparation stays local
and does not authorize declaration, deployment status mutation, declaration
receipt writing, endpoint values, approval references, dates, validation-pass
claims, evidence-ledger append, workflow dispatch, artifact publication,
readiness claims, customer access, money movement, legal/business claims,
publication, or deployment.
Governance scope: Foundation Mode, issue #330 public health declaration
rehearsal, public-safe field labels, private-value exclusion, promotion
blocking, ledger append blocking, approval blocking, publication blocking,
and deployment restraint.
Dependencies: scripts.validate_foundation_public_health_declaration_rehearsal_boundary.
Invariants: declaration field surfaces remain AwaitingEvidence and reject
status drift, value drift, evidence drift, approval drift, publication drift,
and deployment drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_public_health_declaration_rehearsal_boundary import (  # noqa: E402
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
    validate_foundation_public_health_declaration_rehearsal_boundary,
    validate_packet,
)


def test_foundation_public_health_declaration_rehearsal_artifacts_pass() -> None:
    assert validate_foundation_public_health_declaration_rehearsal_boundary() == []


def test_public_health_declaration_witness_has_expected_identity_and_surfaces() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "public health declaration rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert tuple(payload["field_labels"]) == EXPECTED_FIELD_LABELS
    assert payload["next_action"] == EXPECTED_NEXT_ACTION
    assert payload["public_health_declared"] is False
    assert payload["deployment_status_mutation_allowed"] is False
    assert payload["declaration_receipt_written"] is False
    assert payload["deployment_witness_publication_claimed"] is False
    assert payload["public_health_endpoint_value_recorded"] is False
    assert payload["operator_approval_ref_value_recorded"] is False
    assert payload["schema_validation_pass_claimed"] is False
    assert payload["closure_validation_pass_claimed"] is False
    assert payload["endpoint_match_claimed"] is False
    assert payload["evidence_ledger_append_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_doc_contains_field_labels_and_surface_labels() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "public health declaration rehearsal doc")

    for field_label in EXPECTED_FIELD_LABELS:
        assert field_label in doc_text
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        assert surface_label in doc_text


def test_witness_rejects_public_health_status_receipt_witness_and_endpoint_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "public health declaration rehearsal witness")
    candidate = deepcopy(payload)
    candidate["public_health_declared"] = True
    candidate["deployment_status_mutation_allowed"] = True
    candidate["declaration_receipt_written"] = True
    candidate["deployment_witness_publication_claimed"] = True
    candidate["deployment_witness_state_value_recorded"] = True
    candidate["public_health_endpoint_value_recorded"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "public_health_declaration_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_approval_date_validation_dry_run_and_update_results() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "public health declaration rehearsal witness")
    candidate = deepcopy(payload)
    candidate["operator_approval_ref_value_recorded"] = True
    candidate["audited_date_value_recorded"] = True
    candidate["schema_validation_pass_claimed"] = True
    candidate["closure_validation_pass_claimed"] = True
    candidate["endpoint_match_claimed"] = True
    candidate["dry_run_result_recorded"] = True
    candidate["status_update_result_recorded"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "public_health_declaration_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_ledger_workflow_artifact_readiness_and_external_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "public health declaration rehearsal witness")
    candidate = deepcopy(payload)
    candidate["evidence_ledger_append_allowed"] = True
    candidate["workflow_dispatch_allowed"] = True
    candidate["artifact_publication_allowed"] = True
    candidate["readiness_claimed"] = True
    candidate["customer_access_allowed"] = True
    candidate["personal_data_collection_allowed"] = True
    candidate["money_movement_allowed"] = True
    candidate["legal_clearance_claimed"] = True
    candidate["company_formation_claimed"] = True
    candidate["patent_claimed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "public_health_declaration_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_field_label_drift() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "public health declaration rehearsal witness")
    candidate = deepcopy(payload)
    candidate["field_labels"] = list(reversed(candidate["field_labels"]))

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "public_health_declaration_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "public health declaration rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "public_health_declaration_rehearsal_surface_inventory_invalid"
        for finding in findings
    )
    assert any(finding.rule_id == "public_health_declaration_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_url_host_ip_timestamp_or_assignment_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "public health declaration rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "public_health_endpoint=https://gateway.example/health"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "public_health_declaration_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_public_health_or_deployment_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "public health declaration rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "public health is declared and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "public_health_declaration_rehearsal_forbidden_promotion_phrase" for finding in findings)


def test_witness_rejects_extra_next_action_text() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "public health declaration rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = f"{EXPECTED_NEXT_ACTION}; then update deployment status"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "public_health_declaration_rehearsal_root_value_invalid" for finding in findings)


def test_doc_rejects_url_host_ip_timestamp_or_assignment_shape() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "public health declaration rehearsal doc")
    candidate = f"{doc_text}\npublic_health_endpoint=https://gateway.example/health audited_at=2026-06-05\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "public_health_declaration_rehearsal_forbidden_value_pattern" for finding in findings)


def test_doc_requires_every_surface_label() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "public health declaration rehearsal doc")
    candidate = doc_text.replace("Operator approval reference label", "Operator approval label", 1)

    findings = validate_doc_text(candidate)

    assert "Operator approval reference label" in EXPECTED_DOC_SURFACE_LABELS
    assert findings
    assert any(
        finding.rule_id == "foundation_public_health_declaration_rehearsal_doc_surface_missing"
        for finding in findings
    )


def test_doc_rejects_status_update_or_validation_promotion_phrase() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "public health declaration rehearsal doc")
    candidate = f"{doc_text}\nDeployment status is updated and schema validation passed.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "public_health_declaration_rehearsal_forbidden_promotion_phrase" for finding in findings)
