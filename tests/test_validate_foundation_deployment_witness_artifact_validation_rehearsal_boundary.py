"""Tests for the Foundation Mode deployment witness artifact-validation rehearsal validator.

Purpose: prove issue #330 uploaded-artifact validation preparation stays local
and does not authorize artifact download, artifact paths, artifact ids,
artifact digests, schema-validation claims, deployment-claim publication, HMAC
verification, public endpoint proof, closure-validation claims, evidence-ledger
append, workflow-run claims, operator approval, customer access, personal-data
collection, money movement, legal/business claims, publication, or deployment.
Governance scope: Foundation Mode, issue #330, deployment witness
artifact-validation rehearsal, public-safe validation labels, private-value
exclusion, external-evidence blocking, approval blocking, and deployment
restraint.
Dependencies: scripts.validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary.
Invariants: artifact-validation rehearsal surfaces remain AwaitingEvidence and
reject live value drift, artifact evidence drift, HMAC proof drift, endpoint
proof drift, ledger append drift, approval drift, publication drift, and
promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_DOC_SURFACE_LABELS,
    EXPECTED_NEXT_ACTION,
    EXPECTED_SURFACE_NOTES,
    EXPECTED_SURFACES,
    EXPECTED_VALIDATION_LABELS,
    EXPECTED_WITNESS_ID,
    load_json_object,
    load_text,
    validate_doc_text,
    validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary,
    validate_packet,
)


def test_foundation_deployment_witness_artifact_validation_rehearsal_artifacts_pass() -> None:
    assert validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary() == []


def test_artifact_validation_rehearsal_witness_has_expected_identity_and_surfaces() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness artifact-validation rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert tuple(payload["validation_labels"]) == EXPECTED_VALIDATION_LABELS
    assert payload["next_action"] == EXPECTED_NEXT_ACTION
    assert payload["artifact_download_allowed"] is False
    assert payload["artifact_schema_validation_claimed"] is False
    assert payload["deployment_claim_published_claimed"] is False
    assert payload["runtime_hmac_verified"] is False
    assert payload["conformance_hmac_verified"] is False
    assert payload["public_health_endpoint_claimed"] is False
    assert payload["closure_validation_claimed"] is False
    assert payload["evidence_ledger_append_allowed"] is False
    assert payload["workflow_run_claimed"] is False
    assert payload["deployment_allowed"] is False
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_doc_contains_validation_labels_and_surface_labels() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness artifact-validation rehearsal doc")

    for validation_label in EXPECTED_VALIDATION_LABELS:
        assert validation_label in doc_text
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        assert surface_label in doc_text


def test_witness_rejects_artifact_download_path_id_and_digest_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness artifact-validation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["artifact_download_allowed"] = True
    candidate["artifact_path_recorded"] = True
    candidate["artifact_id_recorded"] = True
    candidate["artifact_digest_recorded"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_root_value_invalid"
        for finding in findings
    )


def test_witness_rejects_schema_claim_deployment_claim_hmac_endpoint_and_closure_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness artifact-validation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["artifact_schema_validation_claimed"] = True
    candidate["deployment_claim_published_claimed"] = True
    candidate["runtime_hmac_verified"] = True
    candidate["conformance_hmac_verified"] = True
    candidate["public_health_endpoint_claimed"] = True
    candidate["closure_validation_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_root_value_invalid"
        for finding in findings
    )


def test_witness_rejects_ledger_workflow_operator_customer_money_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness artifact-validation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["evidence_ledger_append_allowed"] = True
    candidate["workflow_run_claimed"] = True
    candidate["operator_approval_claimed"] = True
    candidate["customer_access_allowed"] = True
    candidate["personal_data_collection_allowed"] = True
    candidate["money_movement_allowed"] = True
    candidate["legal_clearance_claimed"] = True
    candidate["company_formation_claimed"] = True
    candidate["patent_claimed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_root_value_invalid"
        for finding in findings
    )


def test_witness_rejects_validation_label_drift() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness artifact-validation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["validation_labels"] = list(reversed(candidate["validation_labels"]))

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_validation_labels_invalid"
        for finding in findings
    )


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness artifact-validation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_surface_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_surface_state_invalid"
        for finding in findings
    )


def test_witness_rejects_weakened_surface_note() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness artifact-validation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "Artifact path label is listed."

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_surface_note_invalid"
        for finding in findings
    )


def test_witness_rejects_live_url_private_path_or_assignment_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness artifact-validation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "artifact_path=C:\\private\\deployment_witness.json"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_forbidden_value_pattern"
        for finding in findings
    )


def test_witness_rejects_artifact_validation_or_publication_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness artifact-validation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "artifact is downloaded and schema validation passed"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_forbidden_promotion_phrase"
        for finding in findings
    )


def test_witness_rejects_extra_next_action_text() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness artifact-validation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = f"{EXPECTED_NEXT_ACTION}; then validate artifact"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_next_action_invalid"
        for finding in findings
    )


def test_doc_rejects_live_url_or_assignment_shape() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness artifact-validation rehearsal doc")
    candidate = f"{doc_text}\nartifact_id=abc123\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_forbidden_value_pattern"
        for finding in findings
    )


def test_doc_requires_every_surface_label() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness artifact-validation rehearsal doc")
    candidate = doc_text.replace("Artifact digest slot", "Artifact hash slot", 1)

    findings = validate_doc_text(candidate)

    assert "Artifact digest slot" in EXPECTED_DOC_SURFACE_LABELS
    assert findings
    assert any(
        finding.rule_id == "foundation_deployment_witness_artifact_validation_rehearsal_doc_surface_missing"
        for finding in findings
    )


def test_doc_rejects_hmac_endpoint_ledger_or_deployment_promotion_phrase() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness artifact-validation rehearsal doc")
    candidate = f"{doc_text}\nRuntime HMAC verified and evidence ledger appended.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_witness_artifact_validation_rehearsal_forbidden_promotion_phrase"
        for finding in findings
    )
